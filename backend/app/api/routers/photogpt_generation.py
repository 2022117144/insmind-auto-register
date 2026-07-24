"""PhotoGPT Image Generation API Route"""
import asyncio
import base64
import hmac
import hashlib
import json
import logging
import os
import subprocess
import time
from datetime import datetime, timedelta
from typing import Optional, List

from curl_cffi import requests
import certifi
# curl_cffi 在中文路径下 SSL 证书加载失败，显式指定证书路径
import os
os.environ.setdefault("SSL_CERT_FILE", "D:/hermes/cacert.pem")
os.environ.setdefault("CURL_CA_BUNDLE", "D:/hermes/cacert.pem")
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import Response
import httpx
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

# 完整浏览器请求头（模拟 Chrome 134）
_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Sec-Ch-Ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Connection": "keep-alive",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

# 完整浏览器 headers，绕过 PhotoGPT WAF/Cloudflare 指纹检测
BROWSER_HEADERS = {
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

# 用于 GET 请求（不含 Content-Type，GET 不需要）
POLL_HEADERS = {k: v for k, v in BROWSER_HEADERS.items() if k.lower() != "content-type"}

# Proxy auto-detect (cached)
_proxy_url: Optional[dict] = None
_proxy_checked = False
def _get_proxy() -> Optional[dict]:
    global _proxy_url, _proxy_checked
    if _proxy_checked:
        return _proxy_url
    _proxy_checked = True
    for p in [7897, 7890]:
        try:
            s = __import__("socket").create_connection(("127.0.0.1", p), timeout=0.5)
            s.close()
            _proxy_url = {"https": f"http://127.0.0.1:{p}", "http": f"http://127.0.0.1:{p}"}
            return _proxy_url
        except:
            continue
    _proxy_url = None
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


async def _upload_data_urls(data_urls: list[str], nc_token: str = "") -> list[str]:
    """将 data URL 上传到 PhotoGPT CDN，返回 CDN 相对路径（用于 input_urls）"""
    if not data_urls:
        return []
    if not nc_token:
        return data_urls  # 没有 nc_token 无法上传

    result: list[str] = []
    for url in data_urls:
        if not url or not url.startswith("data:image/"):
            result.append(url)
            continue
        try:
            mime = url.split(";")[0].split(":")[1]
            ext = mime.split("/")[-1]
            if ext not in ("jpeg", "jpg", "png", "webp"):
                ext = "jpeg"
            raw_b64 = url.split(",", 1)[1]
            img_bytes = base64.b64decode(raw_b64)

            import httpx
            p = _get_proxy()
            proxy_str = str(p.get("https") or p.get("http")) if p else None
            cookies = {"nc_token": nc_token}

            async with httpx.AsyncClient(proxy=proxy_str, timeout=20.0) as c:
                # 1. 拿 presigned OSS URL
                import uuid
                filename = f"{uuid.uuid4().hex[:12]}.{ext}"
                r = await c.post(
                    f"{PHOTOGPT_API}/api/v1/get-sign-url",
                    json={"biz": "user_upload", "files": [{"filename": filename}]},
                    cookies=cookies,
                    headers={"Content-Type": "application/json", "Origin": PHOTOGPT_API, "Referer": f"{PHOTOGPT_API}/ai-models/gpt-image-2"},
                )
                if r.status_code != 200:
                    raise Exception(f"get-sign-url failed: {r.status_code}")
                sign_data = r.json()
                if sign_data.get("code") != 100000:
                    raise Exception(f"get-sign-url api error: {sign_data.get('message')}")
                upload_url = sign_data["data"][0]["url"]
                saved_filename = sign_data["data"][0]["filename"]

                # 2. PUT 上传到 OSS
                r2 = await c.put(upload_url, content=img_bytes, headers={"Content-Type": mime})
                if r2.status_code != 200:
                    raise Exception(f"OSS upload failed: {r2.status_code}")

                # 3. 构建 CDN 相对路径（input_urls 需要这个格式）
                from datetime import date
                today = date.today().strftime("%Y/%m/%d")
                cdn_path = f"/photogpt/user-upload/{today}/{saved_filename}"
                result.append(cdn_path)
                logger.info(f"📤 PhotoGPT CDN upload OK: {cdn_path}")

        except Exception as e:
            logger.warning(f"⚠️ PhotoGPT 图片上传失败: {e}")
            result.append(url)  # 回退 data URL
    return result


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
    result = {
        k: v.isoformat() if isinstance(v, datetime) else v
        for k, v in job.__dict__.items()
        if not k.startswith("_") and k != "sa_instance_state"
    }
    # output_urls / input_urls 存的是 JSON 字符串，需解析为数组
    for field in ("output_urls", "input_urls"):
        raw = result.get(field)
        if isinstance(raw, str):
            try:
                result[field] = json.loads(raw)
            except Exception:
                result[field] = []
    return result

# ── Account Management ───────────────────────────────────────────

async def _acquire_account(db: AsyncSession, _retry: int = 3) -> Optional[PhotoGPTAccount]:
    now = datetime.utcnow()

    # 先清理已耗尽额度的残留账号（防止上次生成后重启导致自动删除没跑）
    await db.execute(
        delete(PhotoGPTAccount).where(
            PhotoGPTAccount.credits_used >= PhotoGPTAccount.credits
        )
    )
    await db.commit()

    # 原子方式：SELECT 一个空闲账号 → 尝试 UPDATE 抢锁（WHERE 带锁条件）
    # 避免 TOCTOU 竞态：两个请求同时读到同一个账号时，只有一个 UPDATE 会生效
    stmt = (
        select(PhotoGPTAccount)
        .where(PhotoGPTAccount.status == "active")
        .where(PhotoGPTAccount.active == True)
        .where(PhotoGPTAccount.credits_used < PhotoGPTAccount.credits)
        .where(PhotoGPTAccount.access_token.isnot(None))
        .where(PhotoGPTAccount.access_token != "")
        .where(
            (PhotoGPTAccount.gen_locked_until.is_(None))
            | (PhotoGPTAccount.gen_locked_until < now)
        )
        .order_by(PhotoGPTAccount.last_used_at.asc().nullsfirst(), PhotoGPTAccount.id.asc())
        .limit(1)
    )
    account = (await db.execute(stmt)).scalars().first()
    if not account:
        return None

    # 原子 UPDATE：只在锁定已过期/为 NULL 时抢到，否则 WHERE 不匹配 → rowcount=0
    result = await db.execute(
        update(PhotoGPTAccount)
        .where(PhotoGPTAccount.id == account.id)
        .where(
            (PhotoGPTAccount.gen_locked_until.is_(None))
            | (PhotoGPTAccount.gen_locked_until < now)
        )
        .values(gen_locked_until=now + timedelta(minutes=10), last_used_at=now)
    )
    await db.commit()

    if result.rowcount == 0:
        # 被别的请求抢先了，递归重试（防深度递归）
        if _retry > 0:
            return await _acquire_account(db, _retry=_retry - 1)
        return None

    await db.refresh(account)
    return account


async def _release_account(account_id: int, db: AsyncSession):
    """生成失败时释放账号锁"""
    from sqlalchemy import update as sql_update
    try:
        await db.execute(
            sql_update(PhotoGPTAccount)
            .where(PhotoGPTAccount.id == account_id)
            .values(gen_locked_until=None)
        )
        await db.commit()
    except Exception:
        pass


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
    """Background poll — 强化的审核拦截检测"""
    cookies = {"nc_token": nc_token}
    no_url_count = 0  # 连续无图片 URL 的轮询次数
    proxy = _get_proxy()
    proxy_str = str(proxy.get("https") or proxy.get("http")) if proxy else None
    for i in range(60):
        await asyncio.sleep(3)
        try:
            async with httpx.AsyncClient(proxy=proxy_str, timeout=20) as c:
                r = await c.get(
                    f"{PHOTOGPT_API}/api/v1/prediction/get-status",
                    params={"project_id": project_id},
                    cookies=cookies,
                    headers=POLL_HEADERS,
                )
                if r.status_code != 200:
                    with open("d:/hermes/poll_debug.log", "a") as f:
                        f.write(f"[{i+1}] NON200 status={r.status_code} body={r.text[:200]}\n")
                    logger.warning(f"POLL_NON200[{i+1}] status={r.status_code} body={r.text[:300]}")
                    continue
                raw_text = r.text
                with open("d:/hermes/poll_debug.log", "a") as f:
                    f.write(f"[{i+1}] nc={nc_token[:10]} pid={project_id[:10]} status=200 body={raw_text[:300]}\n")
                logger.warning(f"POLL_RAW[{i+1}] status=200 body={raw_text[:500]}")
                data = r.json()
                code = data.get("code")

                # ── 100014: project_id 不存在（审核删除 / 过期 / 账号登出） ──
                if code == 100014:
                    no_url_count += 1
                    if no_url_count >= 3:
                        # 连续 3 次 100014 = 项目不可访问
                        async with async_session_factory() as session:
                            await session.execute(
                                update(PhotoGPTJob).where(PhotoGPTJob.id == job_id)
                                .values(status="failed", error_message="项目不存在（可能被审核删除、过期或账号已登出）")
                            )
                            await session.commit()
                        return
                    continue

                if code != 100000:
                    continue

                result = data.get("data", {})
                status_val = result.get("status", 0)
                results_list = result.get("results", [])

                # ── 提取有效图片 URL ──
                output_urls: list[str] = []
                has_audit_text = False
                audit_text = ""
                for img in results_list:
                    url = img.get("url") or img.get("result_content", "")
                    # 检查 result.error 字段（OpenAI/PhotoGPT 显式拒绝）
                    err_text = img.get("error", "")
                    if err_text and not url:
                        has_audit_text = True
                        audit_text = err_text
                    if url:
                        if url.startswith(("http://", "https://", "/", "data:")):
                            if url.startswith("/"):
                                url = f"{PHOTOGPT_CDN}{url}"
                            output_urls.append(url)
                        else:
                            # result_content 是审核文本而非图片 URL
                            has_audit_text = True
                            audit_text = url

                # ✅ SUCCESS: 拿到图片 URL
                if output_urls:
                    async with async_session_factory() as session:
                        await session.execute(
                            update(PhotoGPTJob).where(PhotoGPTJob.id == job_id)
                            .values(status="success", output_urls=json.dumps(output_urls), completed_at=datetime.utcnow())
                        )
                        await session.commit()
                    logger.info(f"PhotoGPT job {job_id} completed: {output_urls}")
                    return

                # 🔴 AUDIT: result_content 返回审核文本
                if has_audit_text:
                    async with async_session_factory() as session:
                        await session.execute(
                            update(PhotoGPTJob).where(PhotoGPTJob.id == job_id)
                            .values(status="failed", error_message=f"图片被审核拦截: {audit_text[:200]}")
                        )
                        await session.commit()
                    return

                # ⚠️ EMPTY RESULT: status≥1 但无任何有效 URL
                # status=1=PhotoGPT说完成但无图, status=2=理论上成功但空结果
                # 不一定是审核拦截——可能是API格式变更、服务端内部错误、或结果URL格式不在预期范围
                if status_val >= 1 and status_val != 3:
                    result_error = result.get("error", "")
                    specific_error = f" (服务端错误: {result_error[:100]})" if result_error else ""
                    async with async_session_factory() as session:
                        await session.execute(
                            update(PhotoGPTJob).where(PhotoGPTJob.id == job_id)
                            .values(status="failed", error_message=f"生成完成但未返回图片URL{specific_error}")
                        )
                        await session.commit()
                    return

                # 🔴 EXPLICIT FAILURE: status=3
                if status_val == 3:
                    error_msg = result.get("error", "生成失败")
                    async with async_session_factory() as session:
                        await session.execute(
                            update(PhotoGPTJob).where(PhotoGPTJob.id == job_id)
                            .values(status="failed", error_message=error_msg)
                        )
                        await session.commit()
                    return

                # ⏳ STILL PROCESSING: status=0 → 累计无结果次数
                no_url_count += 1
                if no_url_count >= 60:  # 3min 还在 status=0 → 超时
                    async with async_session_factory() as session:
                        await session.execute(
                            update(PhotoGPTJob).where(PhotoGPTJob.id == job_id)
                            .values(status="failed", error_message="生成超时（3分钟仍在处理中），可能是服务器负载高或账号异常")
                        )
                        await session.commit()
                    return

        except Exception as e:
            logger.debug(f"Poll {i+1} error for {project_id}: {e}")

    # ⏱ Full timeout after 3min
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

    # 如果自动删除关闭，每天重置额度
    import json as _j
    _cfg_p = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "photogpt_config.json")
    try:
        with open(_cfg_p) as _f:
            _cfg = _j.load(_f)
    except (FileNotFoundError, json.JSONDecodeError):
        _cfg = {}
    if not _cfg.get("auto_delete_on_exhaust", True):
        # 检查是否跨天，跨天则重置
        _today = datetime.utcnow().date()
        _last = account.last_used_at
        if _last and _last.date() < _today:
            account.credits_used = 0
            await db.execute(
                update(PhotoGPTAccount).where(PhotoGPTAccount.id == account.id)
                .values(credits_used=0)
            )
            await db.commit()
            logger.info(f"PhotoGPT account {account.email} daily credits reset")

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
        # 覆盖系统 proxy 环境变量（Docker 遗留的 host.docker.internal 不可达）
        if proxy:
            proxy_str = str(proxy.get("https") or proxy.get("http"))
            os.environ["HTTP_PROXY"] = proxy_str
            os.environ["HTTPS_PROXY"] = proxy_str
        else:
            os.environ.pop("HTTP_PROXY", None)
            os.environ.pop("HTTPS_PROXY", None)
        async with httpx.AsyncClient(proxy=proxy_str if proxy else None, timeout=30) as c:
            nc_token = account.access_token or ""
            if nc_token:
                check_headers = {k: v for k, v in BROWSER_HEADERS.items() if k.lower() != "content-type"}
                check_r = await c.get(
                    f"{PHOTOGPT_API}/api/v1/userinfo",
                    headers=check_headers,
                    cookies={"nc_token": nc_token},
                )
                check_data = check_r.json()
                if check_data.get("code") != 100000:
                    nc_token = ""

            if not nc_token:
                r = await c.post(
                    f"{PHOTOGPT_API}/api/v1/auth/login",
                    json={"email": account.email, "password": account.password or "Test123456!"},
                    headers=BROWSER_HEADERS,
                )
                login_data = r.json()
                if login_data.get("code") != 100000:
                    await _auto_disable_account(account, db, "login_failed")
                    raise HTTPException(status_code=502, detail=f"PhotoGPT 登录失败: {login_data.get('message','')}")

                nc_token = r.cookies.get("nc_token", "")
                if not nc_token:
                    await _release_account(account.id, db)
                    raise HTTPException(status_code=502, detail="登录后未获取到 nc_token")

                await db.execute(
                    update(PhotoGPTAccount).where(PhotoGPTAccount.id == account.id)
                    .values(access_token=nc_token)
                )
                await db.commit()

            t = int(time.time())

            # 上传 data URL 图片到 OSS，换取 CDN URL（图生图支持）
            input_urls = await _upload_data_urls(req.input_urls or [], nc_token)

            handle_params = {
                "input_urls": input_urls,
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
            # NOTE: nc_token 已在登录后存入 cookie jar，curl_cffi 会自动带上
            # 不要传 cookies= 参数，否则会重复发送
            proxy_for_req = proxy_str if proxy else None
            temp_path = None
            try:
                import tempfile
                with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
                    json.dump(handle_params, f, separators=(",", ":"))
                    temp_path = f.name

                curl_cmd = ["curl", "-s", "-X", "POST"]
                if proxy_for_req:
                    curl_cmd += ["-x", proxy_for_req]
                if nc_token:
                    curl_cmd += ["-b", f"nc_token={nc_token}"]
                for k, v in BROWSER_HEADERS.items():
                    curl_cmd += ["-H", f"{k}: {v}"]
                curl_cmd += ["-d", f"@{temp_path}", f"{PHOTOGPT_API}/api/v1/prediction/handle"]

                loop = asyncio.get_event_loop()
                import subprocess as _sp
                result = await loop.run_in_executor(None, lambda: _sp.run(
                    curl_cmd, capture_output=True, text=True, timeout=30
                ))
            finally:
                if temp_path:
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass

            if result.returncode != 0:
                raise HTTPException(status_code=502, detail=f"curl 请求失败: {result.stderr[:200]}")

            gen_data = json.loads(result.stdout) if result.stdout.strip() else {}
            if gen_data.get("code") != 100000:
                err_msg = gen_data.get("message", "")
                if "credits" in err_msg.lower() or "0 credits" in err_msg:
                    await _auto_disable_account(account, db, "insufficient_credits")
                else:
                    await _release_account(account.id, db)
                raise HTTPException(status_code=502, detail=f"PhotoGPT 生成提交失败: {err_msg}")

            project_id = gen_data["data"]["project_id"]

        # Mark submitted
        await db.execute(
            update(PhotoGPTJob).where(PhotoGPTJob.id == job.id)
            .values(status="submitted", project_id=project_id)
        )

        # 每次生成消耗 1 个额度（账号初始 3，可生成 3 次）
        new_credits_used = (account.credits_used or 0) + 1
        await db.execute(
            update(PhotoGPTAccount).where(PhotoGPTAccount.id == account.id).values(
                gen_locked_until=None,
                credits_used=new_credits_used,
            )
        )
        await db.commit()

        # 额度用完 → 根据设置决定是否自动删除
        if new_credits_used >= account.credits:
            # 检查设置
            import json as _json
            _cfg_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "photogpt_config.json")
            _auto_del = True
            try:
                with open(_cfg_path) as _f:
                    _auto_del = _json.load(_f).get("auto_delete_on_exhaust", True)
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            if _auto_del:
                await db.execute(
                    delete(PhotoGPTAccount).where(PhotoGPTAccount.id == account.id)
                )
                await db.commit()
                logger.info(f"PhotoGPT account {account.email} auto-deleted (credits exhausted)")
            else:
                # 不删除，重置额度
                from datetime import date as _date
                await db.execute(
                    update(PhotoGPTAccount).where(PhotoGPTAccount.id == account.id)
                    .values(credits_used=0, last_used_at=datetime.utcnow())
                )
                await db.commit()
                logger.info(f"PhotoGPT account {account.email} credits reset (auto-delete off)")

        # Start polling with nc_token (NOT Bearer token)
        asyncio.create_task(_poll_generation(nc_token, project_id, job.id))
        return PhotoGPTGenerateResponse(success=True, job_id=job.id, project_id=project_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PhotoGPT generate error: {e}")
        await _release_account(account.id, db)
        await db.execute(update(PhotoGPTJob).where(PhotoGPTJob.id == job.id).values(status="failed", error_message=str(e)))
        await db.commit()
        return PhotoGPTGenerateResponse(success=False, error=str(e))


@router.get("/photogpt/generate/jobs")
async def photogpt_list_jobs(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), db: AsyncSession = Depends(get_db)):
    q = select(PhotoGPTJob).order_by(PhotoGPTJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    return [_serialize(j) for j in (await db.execute(q)).scalars().all()]


@router.post("/photogpt/generate/retry")
async def photogpt_retry_job(body: dict, db: AsyncSession = Depends(get_db)):
    job_id = body.get("job_id")
    if not job_id or not isinstance(job_id, int):
        raise HTTPException(status_code=400, detail="需要 job_id 参数")
    logger.warning(f"=== RETRY ROUTE HIT: job_id={job_id} ===")
    """重试失败的 PhotoGPT 生成任务"""
    job = (await db.execute(select(PhotoGPTJob).where(PhotoGPTJob.id == job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.status not in ("failed",):
        raise HTTPException(status_code=400, detail="只有失败的任务可以重试")
    # 清除旧状态，重新提交
    await db.execute(
        update(PhotoGPTJob).where(PhotoGPTJob.id == job_id)
        .values(status="submitting", error_message=None, project_id=None, output_urls=None, completed_at=None, updated_at=datetime.utcnow())
    )
    await db.commit()
    await db.refresh(job)
    return _serialize(job)


@router.delete("/photogpt/generate/jobs/{job_id}")
async def photogpt_delete_job(job_id: int, db: AsyncSession = Depends(get_db)):
    job = (await db.execute(select(PhotoGPTJob).where(PhotoGPTJob.id == job_id))).scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404)
    # 生成中的任务要释放账号锁
    if job.status == "submitting" and job.account_id:
        await db.execute(
            update(PhotoGPTAccount).where(PhotoGPTAccount.id == job.account_id)
            .values(gen_locked_until=None)
        )
    await db.delete(job)
    await db.commit()
    return {"message": "已删除"}


@router.post("/photogpt/generate/jobs/batch-delete")
async def photogpt_batch_delete_jobs(body: dict, db: AsyncSession = Depends(get_db)):
    ids = body.get("ids", [])
    if not ids:
        raise HTTPException(status_code=400)
    # 释放 submitting 任务的账号锁
    submitting_jobs = (await db.execute(
        select(PhotoGPTJob).where(PhotoGPTJob.id.in_(ids), PhotoGPTJob.status == "submitting")
    )).scalars().all()
    for j in submitting_jobs:
        if j.account_id:
            await db.execute(
                update(PhotoGPTAccount).where(PhotoGPTAccount.id == j.account_id)
                .values(gen_locked_until=None)
            )
    r = await db.execute(delete(PhotoGPTJob).where(PhotoGPTJob.id.in_(ids)))
    await db.commit()
    return {"deleted": r.rowcount}


# 简单内存缓存：url → (下载时间戳, bytes)
_image_cache: dict[str, tuple[float, bytes]] = {}
_IMAGE_CACHE_TTL = 600  # 10 分钟


@router.get("/photogpt/image-proxy")
async def photogpt_image_proxy(url: str = Query(...)):
    """代理加载 PhotoGPT CDN 图片"""
    # 缓存命中直接返回
    now = time.time()
    cached = _image_cache.get(url)
    if cached and now - cached[0] < _IMAGE_CACHE_TTL:
        return Response(
            content=cached[1],
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=86400", "X-Cache": "HIT"},
        )

    # 统一走代理（CDN 也需要 proxy 绕过 Cloudflare）
    p = _get_proxy()
    # httpx 0.28.x 要求 proxy 为字符串（非 dict），从 _get_proxy() 返回的 dict 中取值
    proxy_url = str(p.get("https") or p.get("http")) if p else None
    try:
        async with httpx.AsyncClient(proxy=proxy_url, timeout=15.0, follow_redirects=True) as c:
            resp = await c.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://photogpt.io/",
            })

        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail="图片加载失败")

        body = resp.content
        # 写入缓存
        _image_cache[url] = (time.time(), body)
        return Response(
            content=body,
            media_type=resp.headers.get("content-type", "image/png"),
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="图片加载超时")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"图片加载失败: {str(e)}")