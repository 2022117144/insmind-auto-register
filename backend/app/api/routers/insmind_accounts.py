"""insMind 账号管理 API 路由"""

import asyncio
import json
import logging
import os
import re as re_mod
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from app.core import get_db
from app.models.insmind_account import InsMindAccount
from pydantic import BaseModel


def _extract_insmind_message(response_raw: str) -> str:
    """从 insMind SSE 响应中提取多轮对话的文本消息"""
    if not response_raw or response_raw.strip() in ("{}", "[]", "''", '""'):
        return ""
    try:
        data = json.loads(response_raw)
        msgs = data if isinstance(data, list) else [data]
        for msg in msgs:
            content = msg.get("content", {})
            if isinstance(content, dict) and content.get("type") in ("text", "plain"):
                text = content.get("text", "")
                if text:
                    return text[:500]
            if isinstance(content, str) and content:
                return content[:500]
    except Exception:
        pass
    return ""

logger = logging.getLogger(__name__)

router = APIRouter()


# ============ Schemas ============

class InsMindAccountCreate(BaseModel):
    """创建 insMind 账号请求"""
    email: str
    token: str
    refresh_token: str = ""
    user_id: Optional[str] = None
    org_id: Optional[str] = None
    credits: int = 0
    status: str = "active"


def _serialize_account(account) -> dict:
    """将 ORM 对象序列化为 JSON 兼容 dict（避免 Pydantic datetime→str 冲突）"""
    return {
        k: v.isoformat() if isinstance(v, datetime) else v
        for k, v in account.__dict__.items()
        if not k.startswith("_") and k != "sa_instance_state"
    }


class InsMindAccountStats(BaseModel):
    total: int = 0
    active: int = 0
    expired: int = 0
    banned: int = 0


class UpdateTokenRequest(BaseModel):
    """更新 token 请求"""
    token: str


class SyncTokenEntry(BaseModel):
    """同步 token 条目"""
    email: str
    token: str
    credits: int = 0


class SyncTokensRequest(BaseModel):
    """批量同步 tokens 请求"""
    accounts: List[SyncTokenEntry]


class SyncTokensResponse(BaseModel):
    """批量同步 tokens 响应"""
    updated: int


class BatchDeleteRequest(BaseModel):
    """批量删除请求"""
    ids: List[int]


# ============ Routes ============


@router.post("/insmind/accounts", status_code=201)
async def create_insmind_account(
    account_data: InsMindAccountCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建新的 insMind 账号"""
    # 校验 refresh_token（仅警告，不阻止入库）
    if not account_data.refresh_token or account_data.refresh_token.strip() == "":
        logger.warning(f"⚠️ 账号 {account_data.email} 无 refresh_token，过期后无法自动刷新")
        account_data.refresh_token = account_data.refresh_token or ""

    existing = await db.execute(
        select(InsMindAccount).where(InsMindAccount.email == account_data.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Account with this email already exists")

    now = datetime.utcnow()
    account = InsMindAccount(
        email=account_data.email,
        token=account_data.token,
        refresh_token=account_data.refresh_token,
        user_id=account_data.user_id or "",
        org_id=account_data.org_id or "",
        credits=account_data.credits,
        status=account_data.status,
        created_at=now,
        updated_at=now,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)

    # 同步到 insmind2api 池
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as _c:
            _p = {"email": account.email, "token": account.token,
                  "userId": account.user_id or "0", "credits": account.credits,
                  "orgId": account.org_id or ""}
            if account.org_id:
                _p["orgId"] = account.org_id
            if account.refresh_token:
                _p["refreshToken"] = account.refresh_token
            await _c.post("http://127.0.0.1:5105/api/accounts", json=_p)
    except Exception:
        pass

    return _serialize_account(account)


@router.get("/insmind/accounts")
async def list_insmind_accounts(
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """获取 insMind 账号列表"""
    query = select(InsMindAccount)
    if status:
        query = query.where(InsMindAccount.status == status)
    query = query.order_by(InsMindAccount.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    accounts = result.scalars().all()
    # 手动序列化 datetime
    return [
        {k: v.isoformat() if isinstance(v, datetime) else v
         for k, v in a.__dict__.items() if not k.startswith("_") and k != "sa_instance_state"}
        for a in accounts
    ]


@router.get("/insmind/accounts/stats", response_model=InsMindAccountStats)
async def get_insmind_account_stats(
    db: AsyncSession = Depends(get_db),
):
    """获取 insMind 账号统计"""
    total = await db.execute(select(func.count(InsMindAccount.id)))
    active = await db.execute(
        select(func.count(InsMindAccount.id)).where(InsMindAccount.status == "active")
    )
    expired = await db.execute(
        select(func.count(InsMindAccount.id)).where(InsMindAccount.status == "expired")
    )
    banned = await db.execute(
        select(func.count(InsMindAccount.id)).where(InsMindAccount.status == "banned")
    )
    return InsMindAccountStats(
        total=total.scalar() or 0,
        active=active.scalar() or 0,
        expired=expired.scalar() or 0,
        banned=banned.scalar() or 0,
    )


@router.get("/insmind/accounts/{account_id}")
async def get_insmind_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
):
    """获取单个 insMind 账号详情"""
    result = await db.execute(
        select(InsMindAccount).where(InsMindAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return _serialize_account(account)


@router.post("/insmind/accounts/batch-delete")
async def batch_delete_insmind_accounts(
    body: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
):
    """批量删除 insMind 账号"""
    deleted = 0
    for account_id in body.ids:
        result = await db.execute(
            select(InsMindAccount).where(InsMindAccount.id == account_id)
        )
        account = result.scalar_one_or_none()
        if account:
            await db.delete(account)
            deleted += 1
    await db.commit()
    return {"message": f"{deleted} accounts deleted", "deleted": deleted}


@router.delete("/insmind/accounts/{account_id}")
async def delete_insmind_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
):
    """删除 insMind 账号"""
    result = await db.execute(
        select(InsMindAccount).where(InsMindAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    await db.delete(account)
    await db.commit()
    return {"message": "Account deleted", "id": account_id}


# ============ Token 管理 ============


@router.patch("/insmind/accounts/{email}/token")
async def update_insmind_account_token(
    email: str,
    body: UpdateTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """根据 email 更新 token"""
    result = await db.execute(
        select(InsMindAccount).where(InsMindAccount.email == email)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    account.token = body.token
    account.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(account)
    return _serialize_account(account)


@router.post("/insmind/accounts/sync-tokens", response_model=SyncTokensResponse)
async def sync_insmind_account_tokens(
    body: SyncTokensRequest,
    db: AsyncSession = Depends(get_db),
):
    """批量同步 tokens（insmind2api 刷新 token 后调用）"""
    updated = 0
    for entry in body.accounts:
        result = await db.execute(
            select(InsMindAccount).where(InsMindAccount.email == entry.email)
        )
        account = result.scalar_one_or_none()
        if not account:
            continue

        account.token = entry.token
        account.credits = entry.credits
        account.updated_at = datetime.utcnow()
        updated += 1

    await db.commit()
    return SyncTokensResponse(updated=updated)


# ============ 一键注册 ============

class AutoRegisterResponse(BaseModel):
    success: bool
    email: Optional[str] = None
    token: Optional[str] = None
    user_id: Optional[str] = None
    pool_total: int = 0
    error: Optional[str] = None


@router.post("/insmind/accounts/auto-register", response_model=AutoRegisterResponse)
async def auto_register_insmind_account(db: AsyncSession = Depends(get_db)):
    """
    一键注册 insMind 账号：
    1. 自动打开浏览器注册
    2. 提取 token
    3. 自动加入 insmind2api 账号池
    4. 存入本库
    5. 返回结果
    
    注意：此操作需要浏览器交互，耗时约 30-60 秒
    """
    import subprocess

    # 直接硬编码项目根目录路径，避免 dirname 层数算错
    script_path = "E:/视频生成/dreamina-auto-register-main/register_insmind.py"

    # 优先使用 Hermes 的 venv python（已安装所有依赖）
    python_cmd = "E:/视频生成/dreamina-auto-register-main/backend/.venv/Scripts/python.exe"
    
    logger.info("开始自动注册 insMind 账号...")
    
    proc = await asyncio.create_subprocess_exec(
        python_cmd, script_path, "--auto-add",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=os.path.dirname(script_path),
    )

    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=180)
    output = stdout.decode("utf-8", errors="replace") if stdout else ""

    # 解析输出中的 RESULT JSON
    result = {"success": False, "error": "脚本无输出"}
    # 查找 JSON 块（紧凑格式）
    import re as re_mod
    json_match = re_mod.search(r'\{[^{}]*"success"[^{}]*\}', output)
    if json_match:
        try:
            result = json.loads(json_match.group())
        except Exception:
            result = {"success": False, "error": "解析注册结果失败"}

    # 注册成功则存入本库（仅当有 org_id，否则无意义）
    if result.get("success") and result.get("org_id"):
        try:
            refresh_token = result.get("refresh_token", "")
            if not refresh_token or refresh_token.strip() == "":
                logger.warning("⚠️ insMind 未发放 refresh_token（email 注册通常不发），账号将在 8h 后过期")
            from app.models.insmind_account import InsMindAccount
            now = datetime.utcnow()
            account = InsMindAccount(
                email=result.get("email", ""),
                token=result.get("token", ""),
                refresh_token=refresh_token,
                user_id=result.get("userId", "") or "",
                org_id=result.get("org_id", "") or "",
                credits=0,
                status="active",
                created_at=now,
                updated_at=now,
            )
            db.add(account)
            await db.commit()
            logger.info(f"账号已存入本库: {result.get('email')}")
        except Exception as e:
            logger.error(f"存入本库失败: {e}")
            result["success"] = False
            result["error"] = str(e)

    # 查当前池子总数
    pool_total = 0
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            import httpx
            resp = await client.get("http://127.0.0.1:5105/api/accounts")
            if resp.status_code == 200:
                pool_total = resp.json().get("total", 0)
    except Exception:
        pass

    logger.info(f"注册结果: success={result.get('success')}, pool_total={pool_total}")

    return AutoRegisterResponse(
        success=result.get("success", False),
        email=result.get("email"),
        token=result.get("token"),
        user_id=result.get("userId"),
        pool_total=pool_total,
        error=result.get("error"),
    )


# ============ 批量注册 ============


class BatchRegisterResponse(BaseModel):
    total: int
    success: int
    failed: int
    results: List[dict]


@router.post("/insmind/accounts/auto-register-batch", response_model=BatchRegisterResponse)
async def batch_auto_register_insmind(
    count: int = Query(3, ge=1, le=5, description="并发注册数量 (1-5)"),
    db: AsyncSession = Depends(get_db),
):
    """
    批量并发注册 insMind 账号。
    限制最大 5 并发，每个注册使用独立 Playwright 浏览器进程。
    """
    import subprocess
    import asyncio
    import re as re_mod

    script_path = "E:/视频生成/dreamina-auto-register-main/register_insmind.py"
    python_cmd = "E:/视频生成/dreamina-auto-register-main/backend/.venv/Scripts/python.exe"
    MAX_CONCURRENT = 3  # Playwright 很重，限制并发

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async def _run_one() -> dict:
        async with semaphore:
            proc = await asyncio.create_subprocess_exec(
                python_cmd, script_path, "--auto-add",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=os.path.dirname(script_path),
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=180)
                output = stdout.decode("utf-8", errors="replace") if stdout else ""
                result = {"success": False, "error": "No output"}
                json_match = re_mod.search(r'\{[^{}]*"success"[^{}]*\}', output)
                if json_match:
                    try:
                        result = json.loads(json_match.group())
                    except Exception:
                        result = {"success": False, "error": "Parse failed"}
                if result.get("success") and result.get("org_id"):
                    try:
                        now = datetime.utcnow()
                        account = InsMindAccount(
                            email=result.get("email", ""),
                            token=result.get("token", ""),
                            refresh_token=result.get("refresh_token", "") or "",
                            user_id=result.get("userId", "") or "",
                            org_id=result.get("org_id", "") or "",
                            credits=0, status="active",
                            created_at=now, updated_at=now,
                        )
                        db.add(account)
                        await db.commit()
                    except Exception as e:
                        logger.warning(f"批量注册存库失败: {e}")
                elif result.get("success") and not result.get("org_id"):
                    logger.warning(f"⏭️ 账号 {result.get('email')} 无 org_id，跳过入库")
                return result
            except asyncio.TimeoutError:
                proc.kill()
                return {"success": False, "error": "Timeout"}
            except Exception as e:
                return {"success": False, "error": str(e)}

    logger.info(f"🚀 开始批量注册 {count} 个 insMind 账号 (并发 {MAX_CONCURRENT})...")
    tasks = [_run_one() for _ in range(count)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    parsed = []
    for r in results:
        if isinstance(r, dict):
            parsed.append(r)
        else:
            parsed.append({"success": False, "error": str(r)})

    success_count = sum(1 for r in parsed if r.get("success"))
    logger.info(f"批量注册完成: {success_count}/{count} 成功")

    return BatchRegisterResponse(
        total=count,
        success=success_count,
        failed=count - success_count,
        results=parsed,
    )


class InsMindGenerateRequest(BaseModel):
    """insMind 视频生成请求"""
    prompt: str
    model: str = "Pixverse-V6.0"
    duration: int = 10
    resolution: str = "360P"
    aspect_ratio: str = "16:9"
    image_url: Optional[str] = None


class InsMindGenerateResponse(BaseModel):
    success: bool
    task_id: Optional[str] = None
    video_url: Optional[str] = None
    error: Optional[str] = None
    timeout: bool = False


INMIND_VIDEO_TIMEOUT = 200


@router.post("/insmind/generate", response_model=InsMindGenerateResponse)
async def insmind_generate(
    req: InsMindGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """通过 insmind2api 代理生成视频（并发安全）"""
    import httpx as _httpx
    from app.models.insmind_account import InsMindAccount, check_insmind_token_valid
    from sqlalchemy import update as sql_update

    # 先打扫过期账号
    async def _cleanup():
        all_accts = (
            (await db.execute(
                select(InsMindAccount)
            )).scalars().all()
        )
        for a in all_accts:
            if not check_insmind_token_valid(a.token) and not (a.refresh_token and a.refresh_token.strip()):
                await db.delete(a)
                logger.info(f"🧹 清理过期账号: {a.email}")
            elif a.status == "generating":
                await db.execute(
                    sql_update(InsMindAccount)
                    .where(InsMindAccount.id == a.id)
                    .where(InsMindAccount.status == "generating")
                    .values(status="active")
                )
                logger.info(f"🔓 释放卡死账号: {a.email}")
        await db.commit()
    await _cleanup()

    # 1. 原子获取空闲账号
    async def _release():
        try:
            await db.execute(
                sql_update(InsMindAccount)
                .where(InsMindAccount.id == account.id)
                .where(InsMindAccount.status == "generating")
                .values(status="active")
            )
            await db.commit()
        except Exception:
            pass

    account = None
    all_accounts = (
        (await db.execute(
            select(InsMindAccount).where(InsMindAccount.status.in_(["active"])).order_by(InsMindAccount.id)
        )).scalars().all()
    )
    for candidate in all_accounts:
        if not check_insmind_token_valid(candidate.token):
            continue
        await db.execute(
            sql_update(InsMindAccount)
            .where(InsMindAccount.id == candidate.id)
            .where(InsMindAccount.status == "active")
            .values(status="generating")
        )
        await db.commit()
        check = await db.execute(
            select(InsMindAccount).where(InsMindAccount.id == candidate.id)
        )
        updated = check.scalar_one_or_none()
        if updated and updated.status == "generating":
            account = updated
            break
    if not account:
        raise HTTPException(status_code=402, detail="No available insMind accounts")

    # 2. 检查 insmind2api 池里有没有这个账号
    api_email = account.email
    api_token = account.token or ""

    try:
        async with _httpx.AsyncClient(timeout=5.0) as c:
            pool = await c.get("http://127.0.0.1:5105/api/accounts")
            if pool.status_code == 200:
                pool_accounts = pool.json().get("accounts", [])
                if not any(a.get("email") == api_email for a in pool_accounts):
                    await c.post("http://127.0.0.1:5105/api/accounts", json={
                        "email": api_email,
                        "token": api_token,
                        "userId": account.user_id or "0",
                        "credits": account.credits or 0,
                        "orgId": account.org_id or "",
                    })
                    logger.info(f"账号 {api_email} 已加入 insmind2api 池")
    except Exception as e:
        logger.warning(f"同步到 insmind2api 池失败: {e}")

    # 3. 调用 insmind2api 生成视频
    try:
        async with _httpx.AsyncClient(timeout=INMIND_VIDEO_TIMEOUT) as c:
            resp = await c.post(
                "http://127.0.0.1:5105/api/v1/videos/generations",
                json={
                    "prompt": req.prompt,
                    "model": req.model,
                    "duration": req.duration,
                    "resolution": req.resolution,
                    "aspect_ratio": req.aspect_ratio,
                    "image_url": req.image_url,
                },
            )

        if resp.status_code == 200:
            data = resp.json()
            task_id = data.get("id", "")
            video_url = data.get("video_url")
            logger.info(f"视频生成已提交: task_id={task_id}, 账号={api_email}")

            # 🔥 生成成功 → 删除账号
            if video_url:
                try:
                    await db.delete(account)
                    await db.commit()
                    logger.info(f"🗑️ 已从 DB 删除 {api_email}")
                    async with _httpx.AsyncClient(timeout=5.0) as _c:
                        pr = await _c.get("http://127.0.0.1:5105/api/accounts")
                        if pr.status_code == 200:
                            rem = [a for a in pr.json().get("accounts", []) if a.get("email") != api_email]
                            await _c.post("http://127.0.0.1:5105/api/accounts/sync", json={"accounts": rem})
                            logger.info(f"🗑️ 已从池删除 {api_email} (剩 {len(rem)} 个)")
                except Exception as del_err:
                    logger.warning(f"⚠️ 删账号异常: {del_err}")
                return InsMindGenerateResponse(
                    success=True, task_id=task_id, video_url=video_url, error=None,
                )
            else:
                await _release()
                # 尝试解析 insMind 返回的响应，判断是否被审核拦截
                data_str = str(data) if isinstance(data, dict) else ""
                if not data_str.strip() or data_str.strip() in ("{}", "[]"):
                    err_msg = "insMind 未返回任何响应（可能被内容审核拦截，请尝试修改提示词）"
                elif '"type":"plain"' in data_str:
                    err_msg = "insMind 返回文本信息而非视频（可能被审核拦截）"
                elif "invalid_access_token" in data_str.lower():
                    err_msg = "账号 token 已过期，请重新注册"
                else:
                    err_msg = "insMind 未返回视频 URL"
                logger.warning(f"⚠️ 视频生成未返回 URL: {err_msg}")
                return InsMindGenerateResponse(success=False, error=err_msg)
        else:
            error_detail = resp.text[:200]
            logger.error(f"视频生成失败 ({resp.status_code}): {error_detail}")
            await _release()
            return InsMindGenerateResponse(success=False, error=error_detail)

    except _httpx.TimeoutException:
        await _release()
        logger.error(f"视频生成超时 ({INMIND_VIDEO_TIMEOUT}s)")
        return InsMindGenerateResponse(success=False, error="Request timeout", timeout=True)
    except Exception as e:
        await _release()
        logger.error(f"视频生成异常: {e}")
        return InsMindGenerateResponse(success=False, error=str(e))