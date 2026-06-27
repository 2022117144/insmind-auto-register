"""PhotoGPT 账号管理 API 路由"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from pydantic import BaseModel

from app.core import get_db
from app.models.photogpt_account import PhotoGPTAccount

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────

class PhotoGPTAccountCreate(BaseModel):
    email: str
    access_token: str
    password: str = ""
    credits: int = 20


class BatchDeleteRequest(BaseModel):
    ids: List[int]


class AutoRegisterResponse(BaseModel):
    success: bool
    email: str = ""
    access_token: str = ""
    pool_total: int = 0
    error: str = ""


class BatchRegisterResponse(BaseModel):
    total: int
    success: int
    failed: int
    results: list = []


# ── Proxy auto-detect (cached) ──────────────────────────────────

_proxy_url: Optional[str] = None
_proxy_checked = False


def _get_proxy() -> Optional[str]:
    global _proxy_url, _proxy_checked
    if _proxy_checked:
        return _proxy_url
    _proxy_checked = True
    for p in [7897, 7890]:
        try:
            s = __import__("socket").create_connection(("127.0.0.1", p), timeout=0.5)
            s.close()
            _proxy_url = f"http://127.0.0.1:{p}"
            return _proxy_url
        except:
            continue
    _proxy_url = ""
    return None


# ── Serialize ────────────────────────────────────────────────────

def _serialize(account) -> dict:
    return {
        k: v.isoformat() if isinstance(v, datetime) else v
        for k, v in account.__dict__.items()
        if not k.startswith("_") and k != "sa_instance_state"
    }


# ── Registration (with auto-retry on temp-mail domain block) ───

_KNOWN_BLOCKED_DOMAINS: set = set()


def _run_register_sync(password: str, proxy_url: Optional[str] = None, max_retries: int = 3) -> dict:
    """
    同步执行注册。
    自动生成 temp-mail 邮箱 → 注册 → 等验证信 → 确认 → 登录。
    遇到 temp-mail 域名被 PhotoGPT 屏蔽时，换邮箱重试（最多 max_retries 次）。
    """
    import httpx, time, re
    from urllib.parse import urlparse

    HEADERS = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Origin": "https://photogpt.io",
        "Referer": "https://photogpt.io/ai-models/gpt-image-2",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Ch-Ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }

    def _poll_verify(email: str) -> str | None:
        """轮询 temp-mail 收验证信，返回 register_token 或 None"""
        mail_http = httpx.Client(
            base_url="https://api.internal.temp-mail.io",
            timeout=15,
            proxy=proxy_url,
        )
        try:
            domain = email.split("@", 1)[-1] if "@" in email else ""
            for i in range(20):  # ~60s
                time.sleep(3)
                try:
                    r = mail_http.get(f"/api/v3/email/{email}/messages")
                    if r.status_code != 200:
                        continue
                    messages = r.json()
                    if not isinstance(messages, list):
                        continue
                    for msg in messages:
                        sender = msg.get("from_address", "") or msg.get("from", "")
                        subject = msg.get("subject", "")
                        body = msg.get("body_text", "") or msg.get("body_html", "") or ""
                        if "photogpt" not in sender.lower() and "photogpt" not in subject.lower() and "photogpt" not in body.lower():
                            continue
                        match = re.search(r'user-confirm\?token=([^&\s"]+)', body)
                        if not match:
                            match = re.search(r'/user-confirm\?token=([^&\s"]+)', body)
                        if match:
                            return match.group(1)
                except Exception:
                    pass
            # 超时没收到 → 标记该域名可能被屏蔽
            if domain:
                _KNOWN_BLOCKED_DOMAINS.add(domain)
            return None
        finally:
            mail_http.close()

    def _gen_email() -> str | None:
        """从 temp-mail 生成一个新邮箱，跳过已知被屏蔽的域名"""
        mail_http = httpx.Client(
            base_url="https://api.internal.temp-mail.io",
            timeout=15,
            proxy=proxy_url,
        )
        try:
            # 最多试 5 次换域名
            for _ in range(5):
                r = mail_http.post("/api/v3/email/new")
                if r.status_code != 200:
                    continue
                data = r.json()
                email = (data.get("email") or "").strip()
                if not email or "@" not in email:
                    continue
                domain = email.split("@", 1)[-1]
                if domain in _KNOWN_BLOCKED_DOMAINS:
                    continue
                return email
            return None
        finally:
            mail_http.close()

    last_error = ""
    for attempt in range(max_retries):
        # 1. 生成临时邮箱
        email = _gen_email()
        if not email:
            last_error = "无法获取临时邮箱（所有域名均被屏蔽?）"
            continue

        http = httpx.Client(headers=HEADERS, timeout=15, proxy=proxy_url)
        try:
            # 2. Register-apply
            r = http.post(
                "https://photogpt.io/api/v1/auth/register-apply",
                json={"email": email, "password": password},
            )
            resp = r.json()
            if resp.get("code") != 100000:
                last_error = f"注册申请失败: {resp}"
                http.close()
                time.sleep(2)
                continue

            # 3. 等验证邮件
            register_token = _poll_verify(email)
            if not register_token:
                last_error = f"等待验证邮件超时（{email}，域名可能被屏蔽）"
                http.close()
                time.sleep(2)
                continue

            # 4. 确认注册
            r = http.post(
                "https://photogpt.io/api/v1/auth/register",
                json={"register_token": register_token},
            )
            resp = r.json()
            if resp.get("code") != 100000:
                last_error = f"注册确认失败: {resp}"
                http.close()
                continue

            # 5. 登录
            r = http.post(
                "https://photogpt.io/api/v1/auth/login",
                json={"email": email, "password": password},
            )
            resp = r.json()
            if resp.get("code") != 100000:
                last_error = f"登录失败: {resp}"
                http.close()
                continue

            access_token = resp["data"]["access_token"]
            http.close()
            return {"email": email, "access_token": access_token, "password": password}

        except Exception as e:
            last_error = str(e)
            http.close()
            time.sleep(2)
            continue

    return {"error": f"注册失败（已重试 {max_retries} 次）: {last_error}"}


# ── Routes ───────────────────────────────────────────────────────

@router.post("/photogpt/accounts", status_code=201)
async def create_photogpt_account(
    account_data: PhotoGPTAccountCreate,
    db: AsyncSession = Depends(get_db),
):
    """手动添加 PhotoGPT 账号"""
    existing = await db.execute(
        select(PhotoGPTAccount).where(PhotoGPTAccount.email == account_data.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="账号已存在")

    now = datetime.utcnow()
    account = PhotoGPTAccount(
        email=account_data.email,
        access_token=account_data.access_token,
        password=account_data.password,
        credits=account_data.credits,
        status="active",
        created_at=now,
        updated_at=now,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return _serialize(account)


@router.get("/photogpt/accounts")
async def list_photogpt_accounts(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """获取 PhotoGPT 账号列表"""
    query = select(PhotoGPTAccount)
    if status:
        query = query.where(PhotoGPTAccount.status == status)
    query = query.order_by(PhotoGPTAccount.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    accounts = result.scalars().all()
    return [_serialize(a) for a in accounts]


@router.get("/photogpt/accounts/stats")
async def get_photogpt_stats(
    db: AsyncSession = Depends(get_db),
):
    """获取账号统计"""
    total = await db.execute(select(func.count(PhotoGPTAccount.id)))
    active = await db.execute(
        select(func.count(PhotoGPTAccount.id)).where(PhotoGPTAccount.status == "active")
    )
    expired = await db.execute(
        select(func.count(PhotoGPTAccount.id)).where(PhotoGPTAccount.status == "expired")
    )
    banned = await db.execute(
        select(func.count(PhotoGPTAccount.id)).where(PhotoGPTAccount.status == "banned")
    )
    return {
        "total": total.scalar() or 0,
        "active": active.scalar() or 0,
        "expired": expired.scalar() or 0,
        "banned": banned.scalar() or 0,
    }


@router.delete("/photogpt/accounts/{account_id}")
async def delete_photogpt_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PhotoGPTAccount).where(PhotoGPTAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    await db.delete(account)
    await db.commit()
    return {"message": "已删除"}


@router.post("/photogpt/accounts/batch-delete")
async def batch_delete_photogpt(
    body: BatchDeleteRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        delete(PhotoGPTAccount).where(PhotoGPTAccount.id.in_(body.ids))
    )
    await db.commit()
    return {"message": "批量删除完成", "deleted": result.rowcount}


@router.post("/photogpt/accounts/auto-register", response_model=AutoRegisterResponse)
async def auto_register_photogpt(
    db: AsyncSession = Depends(get_db),
):
    """自动注册一个 PhotoGPT 账号（含 temp-mail 域名屏蔽自动重试）"""
    password = "Test123456!"
    proxy = _get_proxy()

    # 执行注册（同步，使用线程池避免阻塞）
    from concurrent.futures import ThreadPoolExecutor
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        result = await loop.run_in_executor(pool, _run_register_sync, password, proxy)

    if "error" in result:
        return AutoRegisterResponse(success=False, error=result["error"])

    # 存入数据库
    now = datetime.utcnow()
    account = PhotoGPTAccount(
        email=result["email"],
        access_token=result["access_token"],
        password=result.get("password", password),
        credits=20,
        status="active",
        created_at=now,
        updated_at=now,
    )
    db.add(account)
    await db.commit()

    # 统计池子大小
    total = await db.execute(select(func.count(PhotoGPTAccount.id)))

    return AutoRegisterResponse(
        success=True,
        email=result["email"],
        access_token=result["access_token"],
        pool_total=total.scalar() or 0,
    )


@router.post("/photogpt/accounts/auto-register-batch", response_model=BatchRegisterResponse)
async def auto_register_batch_photogpt(
    count: int = Query(3, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
):
    """批量注册 PhotoGPT 账号"""
    results = []
    success_count = 0

    for i in range(count):
        try:
            resp = await auto_register_photogpt(db)
            results.append({
                "email": resp.email or "",
                "success": resp.success,
                "error": resp.error or "",
            })
            if resp.success:
                success_count += 1
        except Exception as e:
            results.append({"email": "", "success": False, "error": str(e)})
        
        if i < count - 1:
            await asyncio.sleep(3)  # 避免风控
    
    return BatchRegisterResponse(
        total=count,
        success=success_count,
        failed=count - success_count,
        results=results,
    )