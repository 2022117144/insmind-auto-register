"""
账号管理 API 路由
"""

import csv
import json
import io
import logging
from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from app.core import get_db
from app.core.config import settings
from app.models import Account, ProxyNode
from app.schemas import AccountResponse, AccountDetail, MessageResponse
from app.services.jimeng_api import JimengClient
from app.services.proxy_pool import proxy_pool
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class BatchActionRequest(BaseModel):
    ids: List[int]


class ManualAccountCreate(BaseModel):
    email: str
    region: str
    session_id: str


class ManualImportRequest(BaseModel):
    mode: str
    content: str


class AccountStatsSchema(BaseModel):
    total: int
    success: int
    failed: int
    pending: int
    success_rate: float
    matched: int


async def _preflight_check(proxy_url: str, timeout: float = 5.0) -> bool:
    """
    代理连通性预检：多目标快速检测代理是否可用。
    Returns: True 代理可用, False 不可用
    """
    import httpx

    try:
        async with httpx.AsyncClient(
            proxy=proxy_url, timeout=timeout, verify=False
        ) as client:
            preflight_urls = []
            if settings.ipinfo_token:
                preflight_urls.append(
                    f"https://ipinfo.io/json?token={settings.ipinfo_token}"
                )
            preflight_urls.extend(
                [
                    "https://api.ipify.org?format=json",
                    "https://www.cloudflare.com/cdn-cgi/trace",
                    "https://1.1.1.1/cdn-cgi/trace",
                ]
            )
            for url in preflight_urls:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return True
            return False
    except Exception as e:
        logger.debug(f"代理预检失败 [{proxy_url}]: {e}")
        return False


async def _resolve_clash_proxy_url(node_name: str) -> Optional[str]:
    """切换 Clash 节点并返回代理 URL，失败返回 None"""
    try:
        from app.services.clash_manager import clash_manager

        switched = await clash_manager.switch_node(node_name)
        if switched and settings.clash_proxy_port:
            protocol = settings.clash_proxy_protocol or "http"
            return f"{protocol}://127.0.0.1:{settings.clash_proxy_port}"
    except Exception as e:
        logger.warning(f"Clash 切换节点失败 [{node_name}]: {e}")
    return None


async def resolve_account_proxy(
    account: Account, db: AsyncSession
) -> Tuple[Optional[str], Optional[str]]:
    """
    为账号解析可用的代理 URL 和区域。

    解析优先级（每步含预检，失败则跳到下一步）:
    1. 账号注册时的代理节点（pool 直连 / Clash 切换）
    2. 代理池 fallback（least_used 策略）
    3. 无代理（直连）

    Returns:
        (proxy_url, region)
    """
    proxy_url = None
    region = account.region  # 优先使用数据库已存区域
    proxy_node = None
    fallback_proxy = None

    try:
        if account.proxy_node_name:
            # 查询数据库中的对应代理节点
            stmt = select(ProxyNode).where(ProxyNode.name == account.proxy_node_name)
            r = await db.execute(stmt)
            proxy_node = r.scalar_one_or_none()

            # 从内存代理池查找
            pool_proxy = None
            async with proxy_pool.lock:
                for p in proxy_pool.proxies:
                    if p.name == account.proxy_node_name:
                        pool_proxy = p
                        break

            is_unhealthy = (pool_proxy and pool_proxy.is_healthy is False) or (
                proxy_node and proxy_node.is_healthy is False
            )

            if not is_unhealthy:
                candidate = None
                if pool_proxy and (
                    pool_proxy.group == "external" or pool_proxy.host == "127.0.0.1"
                ):
                    candidate = pool_proxy.url
                elif account.proxy_node_name:
                    candidate = await _resolve_clash_proxy_url(account.proxy_node_name)

                # 预检候选代理
                if candidate and await _preflight_check(candidate):
                    proxy_url = candidate
                elif candidate:
                    logger.warning(
                        f"账号 {account.email} 原始代理预检失败 [{candidate}]，尝试 fallback"
                    )

        # Fallback: 从代理池获取
        if not proxy_url:
            fallback_proxy = await proxy_pool.acquire_proxy(strategy="least_used")
            if fallback_proxy:
                candidate = None
                if (
                    fallback_proxy.group == "external"
                    or fallback_proxy.host == "127.0.0.1"
                ):
                    candidate = fallback_proxy.url
                else:
                    candidate = await _resolve_clash_proxy_url(fallback_proxy.name)

                if candidate and await _preflight_check(candidate):
                    proxy_url = candidate
                elif candidate:
                    logger.warning(f"Fallback 代理预检也失败 [{candidate}]，将使用直连")

        # Region 解析链
        if not region:
            region = (
                await JimengClient.resolve_region_async(proxy_node, db=db)
                if proxy_node
                else JimengClient.resolve_region(account.proxy_node_name)
            )
        if not region:
            region = await JimengClient.resolve_region_by_ip(account.proxy_node_name)

        # 同步 region 到数据库
        if region and region != account.region:
            account.region = region

    finally:
        # 确保释放 fallback 代理
        if fallback_proxy:
            await proxy_pool.release_proxy(fallback_proxy)

    return proxy_url, region


async def resolve_account_proxy_config(
    account: Account, db: AsyncSession
) -> Optional[dict]:
    """
    为浏览器登录解析 Playwright 代理配置。
    每个候选代理会做预检，预检失败则跳到下一个选项。
    返回 Playwright 格式的 proxy dict 或 None。
    """
    fallback_proxy = None
    try:
        if account.proxy_node_name:
            pool_proxy = None
            async with proxy_pool.lock:
                for p in proxy_pool.proxies:
                    if p.name == account.proxy_node_name:
                        pool_proxy = p
                        break

            stmt = select(ProxyNode.is_healthy).where(
                ProxyNode.name == account.proxy_node_name
            )
            r = await db.execute(stmt)
            node_is_healthy = r.scalar_one_or_none()
            is_unhealthy = (pool_proxy and pool_proxy.is_healthy is False) or (
                node_is_healthy is False
            )

            if not is_unhealthy:
                if pool_proxy and (
                    pool_proxy.group == "external" or pool_proxy.host == "127.0.0.1"
                ):
                    # 预检外部代理
                    if await _preflight_check(pool_proxy.url):
                        config = {"server": f"{pool_proxy.host}:{pool_proxy.port}"}
                        if pool_proxy.username:
                            config["username"] = pool_proxy.username
                        if pool_proxy.password:
                            config["password"] = pool_proxy.password
                        return config
                    else:
                        logger.warning(
                            f"外部代理预检失败 [{pool_proxy.name}]，尝试 fallback"
                        )
                else:
                    # Clash 节点切换 + 预检
                    clash_url = await _resolve_clash_proxy_url(account.proxy_node_name)
                    if clash_url and await _preflight_check(clash_url):
                        return {"server": f"127.0.0.1:{settings.clash_proxy_port}"}
                    elif clash_url:
                        logger.warning(
                            f"Clash 代理预检失败 [{account.proxy_node_name}]，尝试 fallback"
                        )

        # Fallback
        fallback_proxy = await proxy_pool.acquire_proxy(strategy="least_used")
        if fallback_proxy:
            if fallback_proxy.group == "external" or fallback_proxy.host == "127.0.0.1":
                if await _preflight_check(fallback_proxy.url):
                    config = {"server": f"{fallback_proxy.host}:{fallback_proxy.port}"}
                    if fallback_proxy.username:
                        config["username"] = fallback_proxy.username
                    if fallback_proxy.password:
                        config["password"] = fallback_proxy.password
                    return config
                else:
                    logger.warning(f"Fallback 外部代理预检失败 [{fallback_proxy.name}]")
            else:
                clash_url = await _resolve_clash_proxy_url(fallback_proxy.name)
                if clash_url and await _preflight_check(clash_url):
                    return {"server": f"127.0.0.1:{settings.clash_proxy_port}"}
                elif clash_url:
                    logger.warning(
                        f"Fallback Clash 代理预检失败 [{fallback_proxy.name}]"
                    )

        logger.warning(f"账号 {account.email} 所有代理预检失败，浏览器将尝试直连")
        return None
    finally:
        if fallback_proxy:
            await proxy_pool.release_proxy(fallback_proxy)


def update_account_credits(account: Account, credits: dict):
    """更新账号积分字段的辅助函数"""
    account.credits_gift = credits.get("gift", 0)
    account.credits_purchase = credits.get("purchase", 0)
    account.credits_vip = credits.get("vip", 0)
    account.credits_total = credits.get("total", 0)
    account.last_credit_check_at = datetime.now()


router = APIRouter()


@router.get("", response_model=List[AccountResponse])
async def list_accounts(
    status: Optional[str] = Query(None, description="系统状态"),
    health_status: Optional[str] = Query(None, description="健康状态"),
    region: Optional[str] = Query(None, description="区域"),
    search: Optional[str] = Query(None, description="邮箱搜索"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    usage_status: Optional[str] = Query(None, description="使用状态"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
):
    """获取账号列表"""
    stmt = select(Account).order_by(Account.created_at.desc())

    if status:
        if status == "success":
            stmt = stmt.where(Account.status.in_(["success", "active"]))
        else:
            stmt = stmt.where(Account.status == status)
    if health_status:
        stmt = stmt.where(Account.health_status == health_status)
    if region and region != "all":
        # 使用 ilike 并添加通配符，以兼容数据库中可能出现的不同格式（如 'hk' 或 'US'）
        stmt = stmt.where(Account.region.ilike(f"%{region}%"))
    if search:
        stmt = stmt.where(Account.email.ilike(f"%{search}%"))
    if start_date:
        stmt = stmt.where(Account.created_at >= start_date)
    if end_date:
        stmt = stmt.where(Account.created_at <= end_date)
    if usage_status and usage_status != "all":
        now_dt = datetime.now()
        if usage_status == "disabled":
            stmt = stmt.where(Account.gen_enabled == False)
        elif usage_status == "in_use":
            stmt = stmt.where(
                Account.gen_enabled == True, Account.gen_locked_until > now_dt
            )
        elif usage_status == "idle":
            stmt = stmt.where(
                Account.gen_enabled == True,
                (Account.gen_locked_until <= now_dt)
                | (Account.gen_locked_until.is_(None)),
            )

    # 结果计数用于前端统计
    count_stmt = select(func.count(Account.id))
    # ... we could return count but response_model is List[AccountResponse]
    # Keep it simple for now as requested

    # 增加分页数到 100 以减少单页展示不足的情况
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(stmt)
    accounts = result.scalars().all()
    # logger.debug(f"List accounts found: {len(accounts)}")
    return accounts


@router.post("/manual", response_model=AccountResponse)
async def create_manual_account(
    payload: ManualAccountCreate, db: AsyncSession = Depends(get_db)
):
    email = payload.email.strip()
    region = _normalize_region_value(payload.region)
    session_id = _normalize_session_value(payload.session_id)
    if not email or not region or not session_id:
        raise HTTPException(
            status_code=400, detail="email/region/sessionid are required"
        )

    exists = (
        await db.execute(select(Account).where(Account.email == email))
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Account already exists")

    account = Account(
        email=email,
        password="manual-import",
        session_id=session_id,
        region=region,
        status="success",
        health_status="unknown",
        gen_enabled=True,
        gen_enabled_at=datetime.now(),
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.post("/manual/import")
async def import_manual_accounts(
    payload: ManualImportRequest, db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    mode = (payload.mode or "").strip().lower()
    content = payload.content or ""
    if mode not in ("csv", "txt"):
        raise HTTPException(status_code=400, detail="mode must be csv or txt")
    if not content.strip():
        raise HTTPException(status_code=400, detail="content is empty")

    if mode == "csv":
        rows = _parse_manual_csv(content)
    else:
        rows = _parse_manual_txt(content)

    success = 0
    skipped = 0
    failed = 0
    errors: List[Dict[str, Any]] = []

    for idx, (email, region, session_id) in enumerate(rows, start=1):
        email = (email or "").strip()
        region = _normalize_region_value(region)
        session_id = _normalize_session_value(session_id)
        if not email or not region or not session_id:
            failed += 1
            errors.append({"line": idx, "email": email, "reason": "missing_fields"})
            continue

        exists = (
            await db.execute(select(Account).where(Account.email == email))
        ).scalar_one_or_none()
        if exists:
            skipped += 1
            continue

        account = Account(
            email=email,
            password="manual-import",
            session_id=session_id,
            region=region,
            status="success",
            health_status="unknown",
            gen_enabled=True,
            gen_enabled_at=datetime.now(),
        )
        db.add(account)
        success += 1

    await db.commit()
    return {
        "success": success,
        "skipped": skipped,
        "failed": failed,
        "errors": errors,
    }


@router.get("/count", response_model=AccountStatsSchema)
async def get_account_stats(
    status: Optional[str] = Query(None),
    health_status: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    usage_status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """获取账号统计"""
    # 基础统计 (全量)，这决定了页面右上角的"总数"
    total = (await db.execute(select(func.count(Account.id)))).scalar() or 0

    # 统一过滤条件，用于计算 matched
    conditions = []

    if status and status != "all":
        if status == "success":
            conditions.append(Account.status.in_(["success", "active"]))
        else:
            conditions.append(Account.status == status)

    if health_status and health_status != "all":
        conditions.append(Account.health_status == health_status)

    if region and region != "all":
        # 支持模糊匹配和忽略大小写
        conditions.append(Account.region.ilike(f"%{region}%"))

    if search:
        conditions.append(Account.email.ilike(f"%{search}%"))

    if start_date:
        conditions.append(Account.created_at >= start_date)

    if end_date:
        conditions.append(Account.created_at <= end_date)

    if usage_status and usage_status != "all":
        now_dt = datetime.now()
        if usage_status == "disabled":
            conditions.append(Account.gen_enabled == False)
        elif usage_status == "in_use":
            conditions.append(Account.gen_enabled == True)
            conditions.append(Account.gen_locked_until > now_dt)
        elif usage_status == "idle":
            conditions.append(Account.gen_enabled == True)
            conditions.append(
                (Account.gen_locked_until <= now_dt)
                | (Account.gen_locked_until.is_(None))
            )

    # 构建应用了过滤条件的查询
    match_stmt = select(func.count(Account.id))
    if conditions:
        for condition in conditions:
            match_stmt = match_stmt.where(condition)

    matched = (await db.execute(match_stmt)).scalar() or 0

    # 计算当前条件下的成功和失败数 (由于前端使用 success_rate 显示当前页面的成功率，所以它也应该基于条件)
    # 如果不存在 conditions，这两个本身也是全量的
    success_stmt = match_stmt.where(Account.status.in_(["success", "active"]))
    failed_stmt = match_stmt.where(Account.status == "failed")

    # 【注意】原逻辑中，因为有些 conditions 中已经指定了 status，再加 status WHERE
    # 如果条件互斥（比如用户选了 status=failed，这里去查 success），结果自然是 0，这是符合预期的正确行为
    success = (await db.execute(success_stmt)).scalar() or 0
    failed = (await db.execute(failed_stmt)).scalar() or 0

    success_rate = (success / matched * 100) if matched > 0 else 0

    return {
        "total": total,
        "success": success,
        "failed": failed,
        # pending=总匹配数-成功-失败
        "pending": matched - success - failed,
        "success_rate": round(success_rate, 1),
        "matched": matched,
    }


@router.get("/export")
async def export_accounts(
    format: str = Query("csv", pattern="^(csv|json)$"),
    status: Optional[str] = None,
    health_status: Optional[str] = None,
    region: Optional[str] = None,
    search: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    usage_status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """导出账号"""
    stmt = select(Account)
    if status:
        if status == "success":
            stmt = stmt.where(Account.status.in_(["success", "active"]))
        else:
            stmt = stmt.where(Account.status == status)
    if health_status:
        stmt = stmt.where(Account.health_status == health_status)
    if region and region != "all":
        stmt = stmt.where(Account.region.ilike(f"%{region}%"))
    if search:
        stmt = stmt.where(Account.email.ilike(f"%{search}%"))
    if start_date:
        stmt = stmt.where(Account.created_at >= start_date)
    if end_date:
        stmt = stmt.where(Account.created_at <= end_date)
    if usage_status and usage_status != "all":
        now_dt = datetime.now()
        if usage_status == "disabled":
            stmt = stmt.where(Account.gen_enabled == False)
        elif usage_status == "in_use":
            stmt = stmt.where(
                Account.gen_enabled == True, Account.gen_locked_until > now_dt
            )
        elif usage_status == "idle":
            stmt = stmt.where(
                Account.gen_enabled == True,
                (Account.gen_locked_until <= now_dt)
                | (Account.gen_locked_until.is_(None)),
            )

    result = await db.execute(stmt)
    accounts = result.scalars().all()

    if format == "json":
        data = [
            {
                "email": a.email,
                "password": a.password,
                "session_id": a.session_id,
                "status": a.status,
                "health_status": a.health_status,
                "region": a.region,
                "is_valid": a.is_valid,
                "credits_total": a.credits_total,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in accounts
        ]
        return data

    # CSV 格式
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Email",
            "Password",
            "SessionId",
            "Status",
            "HealthStatus",
            "Region",
            "IsValid",
            "Credits",
            "CreatedAt",
        ]
    )

    for a in accounts:
        writer.writerow(
            [
                a.email,
                a.password,
                a.session_id,
                a.status,
                a.health_status,
                a.region,
                a.is_valid,
                a.credits_total,
                a.created_at.isoformat() if a.created_at else None,
            ]
        )

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=accounts.csv"},
    )


@router.get("/{account_id}", response_model=AccountDetail)
async def get_account(account_id: int, db: AsyncSession = Depends(get_db)):
    """获取账号详情"""
    stmt = select(Account).where(Account.id == account_id)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    return account


@router.delete("/{account_id}", response_model=MessageResponse)
async def delete_account(account_id: int, db: AsyncSession = Depends(get_db)):
    """删除账号"""
    stmt = select(Account).where(Account.id == account_id)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    await db.delete(account)
    await db.commit()

    return MessageResponse(message="账号已删除")


@router.post("/batch", response_model=MessageResponse)
async def batch_delete_accounts(
    req: BatchActionRequest, db: AsyncSession = Depends(get_db)
):
    """批量删除账号"""
    stmt = delete(Account).where(Account.id.in_(req.ids))
    result = await db.execute(stmt)
    await db.commit()

    return MessageResponse(message=f"已删除 {result.rowcount} 个账号")


@router.post("/batch/refresh-status", response_model=MessageResponse)
async def batch_refresh_status(
    req: BatchActionRequest, db: AsyncSession = Depends(get_db)
):
    """批量刷新状态"""
    stmt = select(Account).where(Account.id.in_(req.ids))
    result = await db.execute(stmt)
    accounts = result.scalars().all()

    success_count = 0
    for account in accounts:
        if not account.session_id:
            continue
        try:
            proxy_url, region = await resolve_account_proxy(account, db)
            client = JimengClient(
                account.session_id, region=region, proxy_url=proxy_url
            )
            is_alive = await client.check_token_status()
            account.health_status = "healthy" if is_alive else "expired"
            if is_alive:
                credits = await client.get_credits()
                if credits:
                    update_account_credits(account, credits)
            account.last_credit_check_at = datetime.now()
            success_count += 1
        except Exception as e:
            logger.exception(f"刷新账号 {account.id} 状态失败: {e}")
            account.health_status = "unknown"

    await db.commit()
    return MessageResponse(message=f"已刷新 {success_count} 个账号状态")


@router.post("/batch/checkin", response_model=MessageResponse)
async def batch_checkin(req: BatchActionRequest, db: AsyncSession = Depends(get_db)):
    """批量签到"""
    stmt = select(Account).where(Account.id.in_(req.ids))
    result = await db.execute(stmt)
    accounts = result.scalars().all()

    checkin_count = 0
    for account in accounts:
        if not account.session_id:
            continue
        try:
            proxy_url, region = await resolve_account_proxy(account, db)
            client = JimengClient(
                account.session_id, region=region, proxy_url=proxy_url
            )
            received = await client.daily_checkin()
            if received is not None:
                account.last_checkin_at = datetime.now()
                if received.get("success"):
                    credits = received.get("credits")
                    if credits:
                        update_account_credits(account, credits)
                else:
                    # 签到返回无积分时，尝试单独获取积分
                    credits = await client.get_credits()
                    if credits:
                        update_account_credits(account, credits)
                checkin_count += 1
        except Exception as e:
            logger.error(f"签到账号 {account.id} 失败: {e}")

    await db.commit()
    return MessageResponse(
        message=f"已尝试签到 {len(accounts)} 个账号，{checkin_count} 个处理完成"
    )


@router.post("/{account_id}/login", response_model=MessageResponse)
async def launch_browser_login(account_id: int, db: AsyncSession = Depends(get_db)):
    """
    启动浏览器登录账号
    使用保存的浏览器状态和相同的代理/指纹
    """
    import asyncio
    from pathlib import Path
    from playwright.async_api import async_playwright

    from app.services.browser_stealth import BrowserStealth

    stmt = select(Account).where(Account.id == account_id)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    if not account.browser_state_path:
        raise HTTPException(status_code=400, detail="无浏览器登录态，请先完成注册")

    state_path = Path(account.browser_state_path)
    if not state_path.exists():
        raise HTTPException(status_code=400, detail="浏览器状态文件不存在")

    # 解析保存的指纹
    fingerprint = None
    if account.fingerprint_json:
        try:
            fingerprint = json.loads(account.fingerprint_json)
        except json.JSONDecodeError:
            pass  # 使用默认指纹

    # 预先解析代理配置（在 db session 还可用时）
    proxy_config = await resolve_account_proxy_config(account, db)

    # 异步启动浏览器
    async def launch_browser_async():
        try:
            async with async_playwright() as p:
                browser_stealth = BrowserStealth(p)

                context = await browser_stealth.create_context(
                    state_path=str(state_path),
                    fingerprint=fingerprint,
                    proxy=proxy_config,
                    headless=False,
                )

                page = await browser_stealth.create_page(context)
                await page.goto(settings.dreamina_url.replace("/ai-tool/login", ""))

                try:
                    # 等待浏览器上下文关闭或页面全部关闭
                    closed_event = asyncio.Event()
                    context.on("close", lambda _: closed_event.set())
                    page.on("close", lambda _: closed_event.set())

                    last_saved_session_id = account.session_id

                    # 定义一个提取和保存状态的函数，进行高频轮询
                    async def save_session_state():
                        nonlocal last_saved_session_id
                        try:
                            # Context 可能已经关闭
                            if not context.pages:
                                return

                            cookies = await context.cookies()
                            new_session_id = None
                            # 优先提取确切的 sessionid
                            for cookie in cookies:
                                if cookie.get("name", "").lower() in (
                                    "sessionid",
                                    "session_id",
                                ):
                                    val = cookie.get("value", "")
                                    if val and val != "0" and len(val) > 10:
                                        new_session_id = val
                                        break

                            # 解析 store-country-code 真实地域
                            real_region = account.region
                            for cookie in cookies:
                                if (
                                    cookie.get("name", "").lower()
                                    == "store-country-code"
                                ):
                                    val = cookie.get("value", "").lower()
                                    if val in ["us", "hk", "jp", "sg", "cn"]:
                                        real_region = val
                                        break
                                elif cookie.get("domain", "").endswith(".sg.jimeng.io"):
                                    real_region = "sg"
                                elif cookie.get("domain", "").endswith(".jp.jimeng.io"):
                                    real_region = "jp"
                                elif cookie.get("domain", "").endswith(".us.jimeng.io"):
                                    real_region = "us"
                                elif cookie.get("domain", "").endswith(".hk.jimeng.io"):
                                    real_region = "hk"

                            # 只有 session_id 发出实质变化，或者是由于目前账号处于不健康状态获取到了新 token 时才写数据库
                            if new_session_id and (
                                new_session_id != last_saved_session_id
                                or account.health_status != "healthy"
                            ):
                                # 保存最新浏览器状态
                                if account.browser_state_path:
                                    await context.storage_state(
                                        path=account.browser_state_path
                                    )

                                from app.core.database import async_session_factory
                                from sqlalchemy import update as sql_update

                                async with async_session_factory() as fresh_db:
                                    await fresh_db.execute(
                                        sql_update(Account)
                                        .where(Account.id == account_id)
                                        .values(
                                            session_id=new_session_id,
                                            full_cookie=json.dumps(cookies),
                                            health_status="healthy",
                                            is_valid="valid",
                                            region=real_region,
                                            last_verified_at=datetime.utcnow(),
                                        )
                                    )
                                    await fresh_db.commit()
                                logger.info(
                                    f"已自动更新账号 {account.email} 状态 [Session: {new_session_id[:5]}*** Region: {real_region}]"
                                )
                                last_saved_session_id = new_session_id
                                account.health_status = "healthy"
                                account.region = real_region
                        except Exception as extract_err:
                            if "Target closed" not in str(
                                extract_err
                            ) and "Browser has been closed" not in str(extract_err):
                                logger.error(f"提取/更新 Session 失败: {extract_err}")

                    # 每 2 秒轮询保存一次，避免用户瞬间关闭杀进程导致拿不到
                    try:
                        for _ in range(900):  # 900 * 2s = 1800s
                            if closed_event.is_set():
                                break
                            await asyncio.sleep(2)
                            await save_session_state()
                    except asyncio.CancelledError:
                        pass
                finally:
                    # 最后确保关闭
                    await context.close()
        except Exception as e:
            logger.error(f"浏览器启动失败: {e}")

    asyncio.create_task(launch_browser_async())
    return MessageResponse(message=f"正在启动浏览器登录 {account.email}")


@router.post("/{account_id}/refresh-status", response_model=AccountDetail)
async def refresh_account_status(account_id: int, db: AsyncSession = Depends(get_db)):
    """刷新账号状态（健康检查 + 获取积分）"""
    stmt = select(Account).where(Account.id == account_id)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    if not account.session_id:
        account.health_status = "unknown"
        await db.commit()
        return account

    proxy_url, region = await resolve_account_proxy(account, db)
    client = JimengClient(account.session_id, region=region, proxy_url=proxy_url)
    is_alive = await client.check_token_status()
    account.health_status = "healthy" if is_alive else "expired"

    if is_alive:
        credits = await client.get_credits()
        if credits:
            update_account_credits(account, credits)

    await db.commit()
    await db.refresh(account)
    return account


@router.post("/{account_id}/checkin", response_model=AccountDetail)
async def account_checkin(account_id: int, db: AsyncSession = Depends(get_db)):
    """账号每日签到"""
    stmt = select(Account).where(Account.id == account_id)
    result = await db.execute(stmt)
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    if not account.session_id:
        raise HTTPException(status_code=400, detail="账号无 Session ID")

    proxy_url, region = await resolve_account_proxy(account, db)
    client = JimengClient(account.session_id, region=region, proxy_url=proxy_url)
    received = await client.daily_checkin()

    if received is not None:
        account.last_checkin_at = datetime.now()
        if received.get("success"):
            credits = received.get("credits")
            if credits:
                update_account_credits(account, credits)
        else:
            credits = await client.get_credits()
            if credits:
                update_account_credits(account, credits)

    await db.commit()
    await db.refresh(account)
    return account


def _normalize_region_value(region: str) -> str:
    return (region or "").strip().lower()


def _normalize_session_value(session_id: str) -> str:
    return (session_id or "").strip()


def _parse_manual_csv(content: str) -> List[Tuple[str, str, str]]:
    rows: List[Tuple[str, str, str]] = []
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        return rows
    headers = {h.strip().lower() for h in reader.fieldnames if h}
    if not {"email", "region", "sessionid"}.issubset(headers):
        raise HTTPException(
            status_code=400, detail="CSV header must include email, region, sessionid"
        )
    for row in reader:
        if not row:
            continue
        email = (row.get("email") or row.get("Email") or "").strip()
        region = (row.get("region") or row.get("Region") or "").strip()
        session_id = (
            row.get("sessionid") or row.get("session_id") or row.get("SessionId") or ""
        ).strip()
        if not email and not region and not session_id:
            continue
        rows.append((email, region, session_id))
    return rows


def _parse_manual_txt(content: str) -> List[Tuple[str, str, str]]:
    rows: List[Tuple[str, str, str]] = []
    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("--")]
        if len(parts) < 3:
            rows.append(("", "", ""))
            continue
        email, region, session_id = parts[0], parts[1], "--".join(parts[2:])
        rows.append((email, region, session_id))
    return rows
