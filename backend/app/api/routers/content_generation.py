"""
Content generation API routes with concurrent account locking.
"""
import json
import logging
import time
import httpx
import asyncio
from datetime import datetime
from collections import Counter
from typing import List, Optional, Any, Mapping, cast

from fastapi import APIRouter, Depends, Query, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, delete

from app.core import get_db, settings
from app.core.database import async_session_factory
from app.models import ContentGenerationJob, Account
from app.schemas import ContentGenerationRequest, ContentGenerationJobResponse
from app.services.content_generation import content_generation_service

import io
import zipfile
from fastapi.responses import StreamingResponse

router = APIRouter()
logger = logging.getLogger(__name__)


def _parse_json_list(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(item) for item in data if item]
    except Exception:
        pass
    return []


def _extract_insmind_message(response_raw: str) -> str:
    """从 insMind SSE 响应中提取多轮对话的文本消息（审核拦截的提示内容）"""
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
                    return text[:500]  # 限长
            # 也查外层 text 字段
            if isinstance(content, str) and content:
                return content[:500]
    except Exception:
        pass
    return ""


def _normalize_region_code(region: Optional[str]) -> str:
    if not region:
        return "cn"
    value = str(region).strip().lower()
    aliases = {
        "usa": "us", "america": "us", "hongkong": "hk", "japan": "jp",
        "singapore": "sg", "taiwan": "tw", "china": "cn", "mainland": "cn",
    }
    return aliases.get(value, value)


async def _resolve_default_generation_region(db: AsyncSession) -> str:
    stmt = select(Account.region).where(
        Account.gen_enabled == True,
        Account.session_id.is_not(None),
        Account.health_status == "healthy",
    )
    rows = (await db.execute(stmt)).all()
    regions = [
        _normalize_region_code(cast(Optional[str], row[0]))
        for row in rows if cast(Optional[str], row[0])
    ]
    if not regions:
        return "cn"
    return Counter(regions).most_common(1)[0][0]


# 并发安全：从 DB 原子获取一个空闲的 insMind 账号，标记为 generating
async def _cleanup_dead_accounts(db: AsyncSession):
    """清理过期且无 refresh_token 的账号（生成前自动打扫）"""
    from app.models.insmind_account import InsMindAccount, check_insmind_token_valid
    from sqlalchemy import update as sql_update

    all_accts = (
        (await db.execute(
            select(InsMindAccount)
        )).scalars().all()
    )
    for acct in all_accts:
        has_rt = bool(acct.refresh_token and acct.refresh_token.strip())
        if not check_insmind_token_valid(acct.token) and not has_rt:
            # token 过期 + 无 refresh_token → 废物，删除
            await db.delete(acct)
            logger.info(f"🧹 清理过期账号: {acct.email} (无 refresh_token)")
        elif acct.status == "generating":
            # 卡在 generating 的账号（上次生成崩溃了），释放
            await db.execute(
                sql_update(InsMindAccount)
                .where(InsMindAccount.id == acct.id)
                .where(InsMindAccount.status == "generating")
                .values(status="active")
            )
            logger.info(f"🔓 释放卡死账号: {acct.email}")
    await db.commit()


async def _aquire_insmind_account(db: AsyncSession):
    """找 token 未过期的 active 账号，原子标记为 generating，返回 None 则无可用账号"""
    from app.models.insmind_account import InsMindAccount, check_insmind_token_valid
    from sqlalchemy import update as sql_update

    # 先打扫
    await _cleanup_dead_accounts(db)

    # 找出已有非终态任务的账号，跳过
    busy_ids = set(
        (await db.execute(
            select(ContentGenerationJob.account_id)
            .where(ContentGenerationJob.status.in_(["queued", "submitting", "submitted", "processing"]))
            .where(ContentGenerationJob.account_id.isnot(None))
        )).scalars().all()
    )

    all_accts = (
        (await db.execute(
            select(InsMindAccount)
            .where(InsMindAccount.status.in_(["active"]))
            .where(InsMindAccount.org_id.isnot(None))
            .where(InsMindAccount.org_id != "")
            .order_by(InsMindAccount.id)
        )).scalars().all()
    )
    for candidate in all_accts:
        if candidate.id in busy_ids:
            continue
        if not check_insmind_token_valid(candidate.token):
            continue
        # 原子标记，防止竞态
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
            return updated
    return None


async def _release_insmind_account(db: AsyncSession, acct) -> None:
    """释放账号锁：恢复为 active（生成失败时调用）"""
    from app.models.insmind_account import InsMindAccount
    from sqlalchemy import update as sql_update
    try:
        await db.execute(
            sql_update(InsMindAccount)
            .where(InsMindAccount.id == acct.id)
            .where(InsMindAccount.status == "generating")
            .values(status="active")
        )
        await db.commit()
        logger.info(f"🔓 账号锁已释放: {acct.email}")
    except Exception as e:
        logger.warning(f"⚠️ 释放账号锁失败: {e}")


async def _delete_insmind_account(db: AsyncSession, acct) -> None:
    """从 DB 删除账号（不再需要同步 insmind2api 池）"""
    try:
        await db.delete(acct)
        await db.commit()
        logger.info(f"🗑️ 已从 DB 删除 {acct.email}")
    except Exception as del_err:
        logger.warning(f"⚠️ 删除账号异常: {del_err}")


def _compress_image_data_url(data_url: str, max_size: int = 2048) -> str:
    """压缩 base64 图片 data URL，最大边不超过 max_size 像素"""
    if not data_url or not data_url.startswith("data:image/"):
        return data_url
    try:
        import base64, io
        from PIL import Image
        fmt = data_url.split(";")[0].split("/")[-1]  # png, jpeg, webp
        raw = base64.b64decode(data_url.split(",", 1)[1])
        img = Image.open(io.BytesIO(raw))
        w, h = img.size
        if max(w, h) <= max_size:
            return data_url  # 已经够小了
        ratio = max_size / max(w, h)
        new_size = (int(w * ratio), int(h * ratio))
        img = img.resize(new_size, Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85)
        b64 = base64.b64encode(out.getvalue()).decode()
        logger.info(f"🖼️ 图片压缩: {w}x{h} → {new_size[0]}x{new_size[1]} ({len(data_url)//1024}KB → {len(b64)//1024}KB)")
        return f"data:image/jpeg;base64,{b64}"
    except Exception as e:
        logger.warning(f"图片压缩失败: {e}")
        return data_url


def _to_job_response(job) -> dict:
    """将 ContentGenerationJob ORM 转为响应 dict"""
    import json as _json
    return {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "prompt": job.prompt,
        "model": job.model,
        "ratio": job.ratio,
        "resolution": job.resolution,
        "duration": job.duration,
        "function_mode": job.function_mode,
        "input_images": _parse_json_list(getattr(job, "input_images", None)),
        "output_urls": _parse_json_list(getattr(job, "output_urls", None)),
        "thumbnail_urls": _parse_json_list(getattr(job, "thumbnail_urls", None)),
        "local_urls": _parse_json_list(getattr(job, "local_urls", None)),
        "error_message": job.error_message,
        "remote_task_id": job.remote_task_id,
        "account_id": job.account_id,
        "created_at": str(getattr(job, "created_at", "")),
        "updated_at": str(getattr(job, "updated_at", "")),
    }


@router.get("/models", response_model=dict)
async def get_generation_models(
    region: Optional[str] = Query(None, description="区域代码，如 cn/us/hk/jp/sg/tw"),
    db: AsyncSession = Depends(get_db),
):
    resolved_region = (
        _normalize_region_code(region)
        if region
        else await _resolve_default_generation_region(db)
    )
    token = f"{resolved_region}-placeholder" if resolved_region != "cn" else "placeholder"

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{settings.jimeng_api_url}/v1/models",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            payload = response.json()
        except Exception:
            from app.models.insmind_account import InsMindAccount
            insmind_count = (await db.execute(select(func.count(InsMindAccount.id)))).scalar() or 0
            if insmind_count > 0:
                payload = {
                    "data": [
                        {"id": "gpt-image-2", "category": "image"},
                        {"id": "Pixverse-V6.0", "category": "video"},
                        {"id": "Kling-3.0", "category": "video"},
                        {"id": "Wan-2.7", "category": "video"},
                        {"id": "Seedance-2.0", "category": "video"},
                        {"id": "Seedance-2.0-Mini", "category": "video"},
                        {"id": "VEO-3.1", "category": "video"},
                    ],
                    "meta": {"country": "insmind", "profile": "insmind", "model_set": "insmind"},
                }
            else:
                raise

    data = payload.get("data") or []
    image_models = [
        str(item.get("id"))
        for item in data
        if item.get("category") == "image" and item.get("id")
    ]
    video_models = [
        str(item.get("id"))
        for item in data
        if item.get("category") == "video" and item.get("id")
    ]
    meta = payload.get("meta") or {}

    return {
        "region": meta.get("country") or resolved_region,
        "profile": meta.get("profile") or resolved_region,
        "model_set": meta.get("model_set") or resolved_region,
        "image_models": image_models,
        "video_models": video_models,
        "source": "jimeng_service",
    }


@router.post("/generate", response_model=ContentGenerationJobResponse)
async def create_generation_job(
    payload: ContentGenerationRequest, db: AsyncSession = Depends(get_db)
):
    if payload.job_type not in ["image", "video"]:
        raise HTTPException(status_code=400, detail="Invalid job type")

    # 🔁 video + 有 insMind 账号 → 走 insmind2api 代理
    from app.models.insmind_account import InsMindAccount
    insmind_count = (
        await db.execute(select(func.count(InsMindAccount.id)))
    ).scalar() or 0

    if payload.job_type == "video" and insmind_count > 0:

        # 1. 原子获取空闲账号（防并发竞态）
        acct = await _aquire_insmind_account(db)
        if not acct:
            raise HTTPException(status_code=402, detail="No available insMind accounts for video generation")

        # 2. 立即创建任务记录，返回前端（异步后台跑 SSE）
        job = ContentGenerationJob(
            job_type="video", status="submitted",
            prompt=payload.prompt, model=payload.model or "Pixverse-V6.0",
            ratio=payload.ratio, resolution=payload.resolution,
            duration=payload.duration, account_id=acct.id,
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)
        job_id = job.id

        # 3. 后台异步执行：调模块 → 更新任务状态
        async def _background_gen():
            nonlocal acct
            from app.core import get_db
            from app.services.insmind_gen import generate_video
            async with async_session_factory() as bg_db:
                try:
                    result = await generate_video(
                        email=acct.email, token=acct.token or "",
                        user_id=acct.user_id or "", org_id=acct.org_id or "",
                        credits=acct.credits or 0,
                        prompt=payload.prompt,
                        model=payload.model or "Pixverse-V6.0",
                        duration=payload.duration or 10,
                        resolution=payload.resolution or "360P",
                        aspect_ratio=payload.ratio or "16:9",
                        input_images=payload.input_images,
                    )

                    logger.info(
                        f"✅ gen result: code={result.code} "
                        f"video_url={result.video_url} email={acct.email}"
                    )

                    if result.code == "success":
                        await bg_db.execute(
                            update(ContentGenerationJob).where(
                                ContentGenerationJob.id == job_id
                            ).values(
                                status="success",
                                output_urls=json.dumps([result.video_url]),
                                remote_task_id=job_id,
                                updated_at=datetime.now(),
                            )
                        )
                        await bg_db.commit()
                        await _delete_insmind_account(bg_db, acct)

                    elif result.code == "function_call":
                        await bg_db.execute(
                            update(ContentGenerationJob).where(
                                ContentGenerationJob.id == job_id
                            ).values(
                                status="processing",
                                error_message=None,
                                remote_task_id=job_id,
                                updated_at=datetime.now(),
                            )
                        )
                        await bg_db.commit()

                    else:
                        # text_reply / failed
                        err_msg = result.message or "未知错误"
                        if result.code == "text_reply":
                            err_msg = f"insMind 回复: {err_msg[:300]}"
                        await bg_db.execute(
                            update(ContentGenerationJob).where(
                                ContentGenerationJob.id == job_id
                            ).values(
                                status="failed",
                                error_message=err_msg,
                                remote_task_id=job_id,
                                updated_at=datetime.now(),
                            )
                        )
                        await bg_db.commit()
                        await _release_insmind_account(bg_db, acct)

                except Exception as e:
                    logger.error(f"SSE 异常 job_id={job_id}: {e}")
                    await bg_db.execute(
                        update(ContentGenerationJob).where(
                            ContentGenerationJob.id == job_id
                        ).values(
                            status="failed",
                            error_message=str(e),
                            updated_at=datetime.now(),
                        )
                    )
                    await bg_db.commit()
                    await _release_insmind_account(bg_db, acct)

        asyncio.create_task(_background_gen())
        return _to_job_response(job)

    # ⬇️ 旧 Dreamina 管线（image + 无 insMind 账号的 video）
    job = ContentGenerationJob(
        job_type=payload.job_type,
        status="queued",
        prompt=payload.prompt,
        model=payload.model,
        ratio=payload.ratio,
        resolution=payload.resolution,
        duration=payload.duration,
        function_mode=payload.function_mode,
        input_images=json.dumps(payload.input_images or [], ensure_ascii=False),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    job_id = cast(int, job.__dict__.get("id", 0))
    await content_generation_service.enqueue(job_id)
    return _to_job_response(job)


# ============ 任务列表管理 ============


@router.get("/jobs", response_model=List[ContentGenerationJobResponse])
async def list_generation_jobs(
    job_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ContentGenerationJob).order_by(ContentGenerationJob.created_at.desc())
    if job_type:
        stmt = stmt.where(ContentGenerationJob.job_type == job_type)
    if status:
        stmt = stmt.where(ContentGenerationJob.status == status)
    result = await db.execute(stmt)
    jobs = result.scalars().all()
    # 异步回填缩略图（不影响返回）
    for job in jobs:
        if job.status == "success":
            output_urls = _parse_json_list(job.output_urls)
            thumbnail_urls = _parse_json_list(job.thumbnail_urls)
            local_urls = _parse_json_list(job.local_urls)
            if content_generation_service.needs_local_backfill(output_urls, thumbnail_urls, local_urls):
                asyncio.create_task(content_generation_service.ensure_local_assets(job.id))
    return [_to_job_response(j) for j in jobs]


@router.get("/jobs/{job_id}", response_model=ContentGenerationJobResponse)
async def get_generation_job(job_id: int, db: AsyncSession = Depends(get_db)):
    job = (
        await db.execute(select(ContentGenerationJob).where(ContentGenerationJob.id == job_id))
    ).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _to_job_response(job)


@router.post("/jobs/{job_id}/cancel", response_model=ContentGenerationJobResponse)
async def cancel_generation_job(job_id: int, db: AsyncSession = Depends(get_db)):
    job = (await db.execute(select(ContentGenerationJob).where(ContentGenerationJob.id == job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status in ["success", "failed", "cancelled"]:
        return _to_job_response(job)
    await db.execute(
        update(ContentGenerationJob).where(ContentGenerationJob.id == job_id).values(status="cancelled", updated_at=datetime.now())
    )
    await db.commit()
    await db.refresh(job)
    return _to_job_response(job)


@router.post("/jobs/{job_id}/retry", response_model=ContentGenerationJobResponse)
async def retry_generation_job(job_id: int, db: AsyncSession = Depends(get_db)):
    job = (await db.execute(select(ContentGenerationJob).where(ContentGenerationJob.id == job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in ("failed", "cancelled"):
        raise HTTPException(status_code=400, detail="Only failed or cancelled jobs can be retried")
    await db.execute(
        update(ContentGenerationJob).where(ContentGenerationJob.id == job_id).values(
            status="queued", error_message=None, output_urls=None, thumbnail_urls=None,
            local_urls=None, remote_task_id=None, account_id=None, finished_at=None, updated_at=datetime.now(),
        )
    )
    await db.commit()
    await db.refresh(job)
    await content_generation_service.enqueue(job_id)
    return _to_job_response(job)


@router.delete("/jobs/{job_id}", response_model=dict)
async def delete_generation_job(job_id: int, db: AsyncSession = Depends(get_db)):
    job = (await db.execute(select(ContentGenerationJob).where(ContentGenerationJob.id == job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    _cleanup_local_files(job)
    await db.delete(job)
    await db.commit()
    return {"message": "ok"}


@router.post("/jobs/batch-delete", response_model=dict)
async def batch_delete_generation_jobs(job_ids: List[int], db: AsyncSession = Depends(get_db)):
    jobs = (await db.execute(select(ContentGenerationJob).where(ContentGenerationJob.id.in_(job_ids)))).scalars().all()
    for job in jobs:
        _cleanup_local_files(job)
    await db.execute(delete(ContentGenerationJob).where(ContentGenerationJob.id.in_(job_ids)))
    await db.commit()
    return {"message": "ok", "deleted": len(job_ids)}


def _cleanup_local_files(job: ContentGenerationJob):
    """删除任务相关的本地文件"""
    import os
    try:
        if job.thumbnail_urls:
            for url in _parse_json_list(job.thumbnail_urls):
                if url and url.startswith("/thumbnails/"):
                    fp = settings.data_dir / "thumbnails" / url.replace("/thumbnails/", "")
                    if fp.exists():
                        os.remove(fp)
        if job.local_urls:
            for url in _parse_json_list(job.local_urls):
                if url and url.startswith("/outputs/"):
                    fp = settings.data_dir / "outputs" / url.replace("/outputs/", "")
                    if fp.exists():
                        os.remove(fp)
    except Exception as e:
        logger.warning(f"清理任务 {job.id} 本地文件失败: {e}")


# ── 图片代理下载 ──────────────────────────────────────────────

# 共享内存缓存（与 image-proxy 共用同一套缓存，URL 相同即命中）
# 从 photogpt_generation 导入同一份缓存
from app.api.routers.photogpt_generation import _image_cache as _shared_image_cache
_download_cache: dict[str, tuple[float, bytes]] = _shared_image_cache
_DOWNLOAD_CACHE_TTL = 600  # 10 分钟


@router.get("/download-proxy")
async def content_download_proxy(url: str = Query(...)):
    """代理下载单张图片，设置 Content-Disposition 触发浏览器下载"""
    # 缓存命中直接返回
    now = time.time()
    cached = _download_cache.get(url)
    if cached and now - cached[0] < _DOWNLOAD_CACHE_TTL:
        filename = url.rsplit("/", 1)[-1].rsplit("?", 1)[0] or "download.png"
        return Response(
            content=cached[1],
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Cache-Control": "public, max-age=86400",
                "X-Cache": "HIT",
            },
        )

    proxy_url = _detect_proxy()
    async with httpx.AsyncClient(proxy=proxy_url, timeout=30.0, follow_redirects=True) as c:
        try:
            resp = await c.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://photogpt.io/",
                },
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail="图片下载失败")
            filename = url.rsplit("/", 1)[-1].rsplit("?", 1)[0] or "download.png"
            body = resp.content
            # 写入缓存
            _download_cache[url] = (time.time(), body)
            return Response(
                content=body,
                media_type=resp.headers.get("content-type", "application/octet-stream"),
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Cache-Control": "public, max-age=86400",
                },
            )
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="图片下载超时")
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"图片下载失败: {str(e)}")


@router.get("/batch-download")
async def content_batch_download(ids: str = Query(...)):
    """批量下载多个任务图片打包为 zip"""
    id_list = [int(x) for x in ids.split(",") if x.strip().isdigit()]
    if not id_list:
        raise HTTPException(status_code=400, detail="无效的 ids 参数")

    proxy_url = _detect_proxy()
    zip_buffer = io.BytesIO()

    async with httpx.AsyncClient(proxy=proxy_url, timeout=30.0, follow_redirects=True) as c:
        try:
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for job_id in id_list:
                    async with async_session_factory() as db:
                        job = (await db.execute(
                            select(ContentGenerationJob).where(ContentGenerationJob.id == job_id)
                        )).scalar_one_or_none()
                    if not job:
                        continue
                    urls = _parse_json_list(getattr(job, "output_urls", None))
                    for idx, img_url in enumerate(urls):
                        try:
                            resp = await c.get(img_url, headers={
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                            })
                            if resp.status_code == 200:
                                ext = (resp.headers.get("content-type", "").split("/")[-1] or "png").split(";")[0]
                                arcname = f"job_{job_id}_{idx + 1}.{ext}"
                                zf.writestr(arcname, resp.content)
                        except Exception:
                            continue
            zip_buffer.seek(0)
            return StreamingResponse(
                zip_buffer,
                media_type="application/zip",
                headers={"Content-Disposition": f'attachment; filename="images_batch_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip"'},
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"打包下载失败: {str(e)}")


def _detect_proxy() -> Optional[str]:
    """本地代理探测，返回单个代理 URL 字符串"""
    for p in [7897, 7890]:
        try:
            s = __import__("socket").create_connection(("127.0.0.1", p), timeout=0.5)
            s.close()
            return f"http://127.0.0.1:{p}"
        except Exception:
            continue
    return None

