"""PhotoGPT Image Generation API Route"""
import asyncio
import hmac
import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, List

import httpx
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, delete

from app.core import get_db, settings
from app.core.database import async_session_factory
from app.models.photogpt_job import PhotoGPTJob
from app.models.photogpt_account import PhotoGPTAccount
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

PHOTOGPT_IMAGE_KEY = "nc_tianyaoxiayu_a9c2d_pred_aa91bc7-fandehen-4d2fa8c1b9_pg-prod"
PHOTOGPT_API = "https://photogpt.io"
PHOTOGPT_CDN = "https://cdn.static-boost.com"

# Proxy auto-detect (cached)
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

# ── Schemas ──────────────────────────────────────────────────────

class PhotoGPTGenerateRequest(BaseModel):
    prompt: str
    aspect_ratio: str = "1:1"
    output_num: int = 1
    quality: str = "medium"
    resolution: str = "1K"
    input_urls: List[str] = []

class PhotoGPTGenerateResponse(BaseModel):
    success: bool
    job_id: Optional[int] = None
    project_id: Optional[str] = None
    error: str = ""

# ── Sign & Helpers ──────────────────────────────────────────────

def _compute_sign(params: dict, key: str) -> str:
    keys = sorted(k for k in params if params[k] is not None)
    parts = []
    for k in keys:
        v = params[k]
        if isinstance(v, (dict, list)):
            v = json.dumps(v, separators=(",", ":"))
        parts.append(f"{k}={v}")
    return hmac.new(key.encode(), "&".join(parts).encode(), hashlib.sha256).hexdigest()

def _serialize(job) -> dict:
    return {
        k: v.isoformat() if isinstance(v, datetime) else v
        for k, v in job.__dict__.items()
        if not k.startswith("_") and k != "sa_instance_state"
    }

# ── Account Management ───────────────────────────────────────────

async def _acquire_account(db: AsyncSession) -> Optional[PhotoGPTAccount]:
    now = datetime.utcnow()
    stmt = (
        select(PhotoGPTAccount)
        .where(PhotoGPTAccount.status == "active")
        .where(PhotoGPTAccount.active == True)
        .where(PhotoGPTAccount.credits_used < PhotoGPTAccount.credits)
        .where(PhotoGPTAccount.access_token.isnot(None))
        .where(PhotoGPTAccount.access_token != "")
        .order_by(PhotoGPTAccount.last_used_at.asc().nullsfirst(), PhotoGPTAccount.id.asc())
    )
    accounts = (await db.execute(stmt)).scalars().all()
    for account in accounts:
        locked_until = getattr(account, "gen_locked_until", None)
        if locked_until and locked_until > now:
            continue
        await db.execute(
            update(PhotoGPTAccount)
            .where(PhotoGPTAccount.id == account.id)
            .values(gen_locked_until=now + timedelta(minutes=10), last_used_at=now)
        )
        await db.commit()
        await db.refresh(account)
        return account
    return None

async def _auto_disable_account(account: PhotoGPTAccount, db: AsyncSession, reason: str):
    await db.execute(
        update(PhotoGPTAccount)
        .where(PhotoGPTAccount.id == account.id)
        .values(
            status="expired" if reason == "insufficient_credits" else "banned",
            active=False,
        )
    )
    await db.commit()

# ── Polling ─────────────────────────────────────────────────────

async def _poll_generation(nc_token: str, project_id: str, job_id: int):
    """Backgroup poll using nc_token cookie (not Bearer token, which PhotoGPT rejects)"""
    cookies = {"nc_token": nc_token}
    for i in range(60):
        await asyncio.sleep(3)
        try:
            async with httpx.AsyncClient(timeout=15, proxy=_get_proxy()) as c:
                r = await c.get(
                    f"{PHOTOGPT_API}/api/v1/prediction/get-status",
                    params={"project_id": project_id},
                    cookies=cookies,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Origin": PHOTOGPT_API,
                        "Referer": f"{PHOTOGPT_API}/ai-models/gpt-image-2",
                    },
                )
                if r.status_code != 200:
                    continue
                data = r.json()
                code = data.get("code")
                if code == 100014:
                    # PhotoGPT 临时不可用，继续轮询（不删除账号）
                    continue
                if code != 100000:
                    continue
                result = data.get("data", {})
                status_val = result.get("status", 0)
                results_list = result.get("results", [])

                # Success: status=2 or has result_content/url
                if status_val == 2 or (results_list and (results_list[0].get("result_content") or results_list[0].get("url"))):
                    output_urls = []
                    for img in results_list:
                        url = img.get("url") or img.get("result_content", "")
                        if url:
                            if url.startswith("/"):
                                url = f"{PHOTOGPT_CDN}{url}"
                            output_urls.append(url)
                    async with async_session_factory() as session:
                        await session.execute(
                            update(PhotoGPTJob).where(PhotoGPTJob.id == job_id)
                            .values(status="success", output_urls=json.dumps(output_urls), completed_at=datetime.utcnow())
                        )
                        await session.commit()
                    logger.info(f"PhotoGPT job {job_id} completed: {output_urls}")
                    return

                elif status_val == 3:
                    error_msg = result.get("error", "生成失败")
                    async with async_session_factory() as session:
                        await session.execute(
                            update(PhotoGPTJob).where(PhotoGPTJob.id == job_id)
                            .values(status="failed", error_message=error_msg)
                        )
                        await session.commit()
                    return

        except Exception as e:
            logger.debug(f"Poll {i+1} error for {project_id}: {e}")

    # Timout after 3min
    async with async_session_factory() as session:
        await session.execute(
            update(PhotoGPTJob).where(PhotoGPTJob.id == job_id)
            .values(status="failed", error_message="轮询超时")
        )
        await session.commit()

# ── Routes ───────────────────────────────────────────────────────

@router.post("/photogpt/generate", response_model=PhotoGPTGenerateResponse)
async def photogpt_generate(req: PhotoGPTGenerateRequest, db: AsyncSession = Depends(get_db)):
    if not req.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt 不能为空")

    account = await _acquire_account(db)
    if not account:
        raise HTTPException(status_code=503, detail="没有可用 PhotoGPT 账号")

    now = datetime.utcnow()
    job = PhotoGPTJob(
        status="submitting",
        prompt=req.prompt,
        aspect_ratio=req.aspect_ratio,
        resolution=req.resolution,
        quality=req.quality,
        output_num=req.output_num,
        input_urls=json.dumps(req.input_urls) if req.input_urls else None,
        account_id=account.id,
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    try:
        proxy = _get_proxy()
        async with httpx.AsyncClient(timeout=15, proxy=proxy) as c:
            # Login — capture nc_token cookie
            r = await c.post(
                f"{PHOTOGPT_API}/api/v1/auth/login",
                json={"email": account.email, "password": account.password or "Test123456!"},
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Origin": PHOTOGPT_API,
                },
            )
            login_data = r.json()
            if login_data.get("code") != 100000:
                await _auto_disable_account(account, db, "login_failed")
                raise HTTPException(status_code=502, detail=f"PhotoGPT 登录失败: {login_data.get('message','')}")

            # Get nc_token from cookies (NOT Bearer token — PhotoGPT uses cookies!)
            nc_token = c.cookies.get("nc_token", "")
            if not nc_token:
                raise HTTPException(status_code=502, detail="登录后未获取到 nc_token")

            t = int(time.time())
            handle_params = {
                "input_urls": req.input_urls or [],
                "type": 61,
                "user_prompt": req.prompt,
                "sub_type": 23,
                "aspect_ratio": req.aspect_ratio,
                "output_num": req.output_num,
                "quality": req.quality,
                "resolution": req.resolution,
                "sig_version": "v1",
                "t": t,
            }
            handle_params["sign"] = _compute_sign(handle_params, PHOTOGPT_IMAGE_KEY)

            # Submit handle — auth via nc_token cookie, NOT Bearer header
            r2 = await c.post(
                f"{PHOTOGPT_API}/api/v1/prediction/handle",
                json=handle_params,
                cookies={"nc_token": nc_token},
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Origin": PHOTOGPT_API,
                    "Referer": f"{PHOTOGPT_API}/ai-models/gpt-image-2",
                },
            )
            gen_data = r2.json()
            if gen_data.get("code") != 100000:
                err_msg = gen_data.get("message", "")
                if "credits" in err_msg.lower() or "0 credits" in err_msg:
                    await _auto_disable_account(account, db, "insufficient_credits")
                raise HTTPException(status_code=502, detail=f"PhotoGPT 生成提交失败: {err_msg}")

            project_id = gen_data["data"]["project_id"]

        # Mark submitted
        await db.execute(
            update(PhotoGPTJob).where(PhotoGPTJob.id == job.id)
            .values(status="submitted", project_id=project_id)
        )
        account.credits_used = (account.credits_used or 0) + 1
        await db.execute(
            update(PhotoGPTAccount).where(PhotoGPTAccount.id == account.id).values(gen_locked_until=None)
        )
        await db.commit()

        # Start polling with nc_token (NOT Bearer token)
        asyncio.create_task(_poll_generation(nc_token, project_id, job.id))
        return PhotoGPTGenerateResponse(success=True, job_id=job.id, project_id=project_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PhotoGPT generate error: {e}")
        await db.execute(update(PhotoGPTJob).where(PhotoGPTJob.id == job.id).values(status="failed", error_message=str(e)))
        await db.commit()
        return PhotoGPTGenerateResponse(success=False, error=str(e))


@router.get("/photogpt/generate/jobs")
async def photogpt_list_jobs(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), db: AsyncSession = Depends(get_db)):
    q = select(PhotoGPTJob).order_by(PhotoGPTJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    return [_serialize(j) for j in (await db.execute(q)).scalars().all()]


@router.delete("/photogpt/generate/jobs/{job_id}")
async def photogpt_delete_job(job_id: int, db: AsyncSession = Depends(get_db)):
    job = (await db.execute(select(PhotoGPTJob).where(PhotoGPTJob.id == job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404)
    await db.delete(job)
    await db.commit()
    return {"message": "已删除"}


@router.post("/photogpt/generate/jobs/batch-delete")
async def photogpt_batch_delete_jobs(body: dict, db: AsyncSession = Depends(get_db)):
    ids = body.get("ids", [])
    if not ids:
        raise HTTPException(status_code=400)
    r = await db.execute(delete(PhotoGPTJob).where(PhotoGPTJob.id.in_(ids)))
    await db.commit()
    return {"deleted": r.rowcount}