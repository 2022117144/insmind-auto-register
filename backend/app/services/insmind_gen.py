"""
insMind 视频生成模块 — 纯过程层
职责：调 insmind2api → 返回结构化结果 InsMindResult
不涉及 DB 操作，不涉及账号生命周期管理

子过程完全独立，不共享 SSE 解析逻辑：
  generate_text_to_video  — 文生视频
  generate_image_to_video — 图生视频
共用：sync_account_to_pool、InsMindResult、_parse_insmind_response
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import timezone, datetime
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

INSMIND2API_URL = "http://127.0.0.1:5105"

# ============ 结果结构体 ============


@dataclass
class InsMindResult:
    code: str  # success / function_call / text_reply / failed
    video_url: Optional[str] = None
    thread_id: Optional[str] = None
    message: Optional[str] = None
    raw_response: Optional[str] = None
    task_id: Optional[str] = None


# ============ 公用工具（真共享） ============


def _compress_image(data_url: str, max_size: int = 2048) -> str:
    """压缩 base64 图片 data URL（仅图生视频用，但做层函数复用即可）"""
    if not data_url or not data_url.startswith("data:image/"):
        return data_url
    try:
        import base64, io
        from PIL import Image

        raw = base64.b64decode(data_url.split(",", 1)[1])
        img = Image.open(io.BytesIO(raw))
        w, h = img.size
        if max(w, h) <= max_size:
            return data_url
        ratio = max_size / max(w, h)
        new_size = (int(w * ratio), int(h * ratio))
        img = img.resize(new_size, Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85)
        b64 = base64.b64encode(out.getvalue()).decode()
        logger.info(
            f"🖼️ 压缩: {w}x{h} → {new_size[0]}x{new_size[1]} "
            f"({len(data_url)//1024}KB → {len(b64)//1024}KB)"
        )
        return f"data:image/jpeg;base64,{b64}"
    except Exception as e:
        logger.warning(f"⚠️ 图片压缩失败: {e}")
        return data_url


def _parse_insmind_response(data: dict) -> InsMindResult:
    """
    解析 insmind2api 返回的统一响应。
    data：{id, video_url, response, ...}
    sse_text 由各子过程传入（各自用自己的解析逻辑），此处不再自行提取。
    """
    video_url = data.get("video_url")
    task_id = data.get("id", "")
    raw_response = data.get("response", "")
    status = data.get("status", "")

    # 有视频 URL → 成功
    if video_url:
        return InsMindResult(
            code="success", video_url=video_url,
            task_id=task_id, raw_response=raw_response,
        )

    # 状态为 processing → 仍在处理中，不是失败
    if status == "processing":
        return InsMindResult(
            code="processing", task_id=task_id,
            raw_response=raw_response,
            message="视频仍在生成中",
        )

    # function_call 检测
    raw_str = str(data)
    if '"function_call"' in raw_str or '"type":"function_call"' in raw_str:
        tid = task_id
        if not tid:
            try:
                if isinstance(raw_response, str) and raw_response:
                    parsed = json.loads(raw_response)
                    if isinstance(parsed, list) and parsed:
                        tid = parsed[0].get("thread_id", task_id)
            except Exception:
                pass
        return InsMindResult(
            code="function_call", thread_id=tid or task_id,
            task_id=task_id, raw_response=raw_response,
        )

    # 其他失败：message 由各子过程自行填入
    return InsMindResult(
        code="failed", message="insMind 未返回视频 URL",
        task_id=task_id, raw_response=raw_response,
    )


# ============ 账号同步 ============


async def sync_account_to_pool(
    email: str, token: str, user_id: str,
    credits: int = 0, org_id: str = "",
) -> None:
    """确保账号在 insmind2api 池里"""
    import os as _os
    _saved = {k: _os.environ.pop(k, None) for k in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy','ALL_PROXY','all_proxy']}
    try:
        async with httpx.AsyncClient(timeout=5.0, trust_env=False) as c:
            pool = await c.get(f"{INSMIND2API_URL}/api/accounts")
            if pool.status_code == 200:
                data = pool.json()
                pool_accounts = data if isinstance(data, list) else data.get("accounts", [])
                if not any(a.get("email") == email for a in pool_accounts):
                    await c.post(f"{INSMIND2API_URL}/api/accounts", json={
                        "email": email, "token": token,
                        "userId": user_id or "0", "credits": credits,
                        "orgId": org_id or "",
                    })
                    logger.info(f"✅ 账号 {email} 已同步到池")
    except Exception as e:
        logger.warning(f"⚠️ 同步池子失败: {e}")
    finally:
        for k, v in _saved.items():
            if v is not None:
                _os.environ[k] = v


# ============ SSE 文本提取（各自一份） ============


def _text_extract_sse(response_raw: str) -> str:
    """文生视频的 SSE 文本提取"""
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


def _image_extract_sse(response_raw: str) -> str:
    """图生视频的 SSE 文本提取（副本，未来可单独演进）"""
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


# ============ 文生视频 ============


async def generate_text_to_video(
    *,
    email: str,
    token: str,
    user_id: str,
    org_id: str,
    credits: int = 0,
    prompt: str,
    model: str = "Pixverse-V6.0",
    duration: int = 10,
    resolution: str = "360P",
    aspect_ratio: str = "16:9",
) -> InsMindResult:
    """文生视频：单轮 SSE，调 generations 端点"""
    await sync_account_to_pool(email, token, user_id, credits, org_id)

    import os as _os2, subprocess as _sp2, json as _j2
    _saved2 = {k: _os2.environ.pop(k, None) for k in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy','ALL_PROXY','all_proxy']}
    try:
        _payload2 = _j2.dumps({
            "prompt": prompt, "model": model,
            "duration": duration, "resolution": resolution,
            "aspect_ratio": aspect_ratio,
        })
        _r2 = _sp2.run(["curl", "-s", "-X", "POST", f"{INSMIND2API_URL}/api/v1/videos/generations",
            "-H", "Content-Type: application/json", "-d", _payload2],
            capture_output=True, text=True, timeout=300)
        if _r2.returncode != 0:
            return InsMindResult(code="failed", message=f"curl 失败: {_r2.stderr[:200]}")
        resp_data = _j2.loads(_r2.stdout)
        task_id = resp_data.get("task_id", "")
        if not task_id:
            return InsMindResult(code="failed", message="5105 未返回 task_id")
        # 轮询结果
        for _ in range(12):
            await asyncio.sleep(15)
            _pr2 = _sp2.run(["curl", "-s", f"{INSMIND2API_URL}/api/v1/tasks/{task_id}"],
                capture_output=True, text=True, timeout=10)
            if _pr2.returncode == 0:
                _pd2 = _j2.loads(_pr2.stdout)
                _pr22 = _pd2.get("result", _pd2)
                _pu2 = _pr22.get("video_url")
                if _pu2:
                    return InsMindResult(code="success", video_url=_pu2, task_id=task_id)
                _ps2 = _pr22.get("status", "")
                if _ps2 == "failed" or _pr22.get("error"):
                    return InsMindResult(code="failed", message=f"5105 返回失败: {_pr22.get('error', '')}")
        return InsMindResult(code="failed", message="轮询超时")
    except Exception as e:
        return InsMindResult(code="failed", message=f"insmind2api 请求异常: {e}")
    finally:
        for k, v in _saved2.items():
            if v is not None:
                _os2.environ[k] = v

# ============ STS 凭证获取（供 shared oss_upload 使用） ============


async def _get_account_sts() -> Optional[dict]:
    """从数据库取一个 insMind 账号，获取 STS 上传凭证"""
    from app.core.database import async_session_factory
    from app.models.insmind_account import InsMindAccount
    from sqlalchemy import select
    try:
        async with async_session_factory() as db:
            acct = (await db.execute(
                select(InsMindAccount)
                .where(InsMindAccount.status == "active")
                .where(InsMindAccount.token.isnot(None))
                .where(InsMindAccount.token != "")
                .limit(1)
            )).scalar_one_or_none()
            if not acct:
                logger.warning("⚠️ 没有可用 insMind 账号获取 STS")
                return None
            token = acct.token or ""
            org_id = acct.org_id or ""
    except Exception as e:
        logger.warning(f"⚠️ 取 insMind 账号失败: {e}")
        return None

    # 解码 JWT payload 拿 inner access_token
    try:
        padded = token + "=" * (4 - len(token) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        inner_token = payload.get("access_token", "")
    except Exception as e:
        logger.warning(f"⚠️ token 解码失败: {e}")
        return None

    if not inner_token:
        return None

    try:
        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as c:
            sts_resp = await c.post(
                "https://www.insmind.com/api/tb-dam/asset/upload/tokens",
                json={"format": "jpg", "content_id": "", "dir": "", "device_id": "python-upload"},
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {inner_token}",
                    "x-product-type": "INDIVIDUAL_FREE",
                    "x-channel-id": "781",
                    "x-business-id": "124",
                    "x-device-id": "python-upload",
                    "origin": "https://www.insmind.com",
                    "referer": "https://www.insmind.com/creation",
                    "Cookie": f"token.prod={token}; token.org_id.prod={org_id}",
                },
            )
        if sts_resp.status_code != 200:
            logger.warning(f"⚠️ STS 失败: {sts_resp.status_code}")
            return None
        return sts_resp.json()
    except Exception as e:
        logger.warning(f"⚠️ STS 请求异常: {e}")
        return None


# ============ OSS 上传（curl.exe） ============


async def _upload_to_oss(
    data_url: str,
    email: str,
    token: str,
    user_id: str,
    org_id: str,
) -> Optional[str]:
    """
    用 curl.exe 上传图片到 insMind OSS，返回 CDN URL。
    curl.exe 用 Windows 原生 TLS (Schannel)，能兼容阿里云 OSS。
    """
    # 1. 解码 data URL
    if not data_url.startswith("data:image/"):
        return None
    try:
        mime = data_url.split(";")[0].split(":")[1]
        ext = mime.split("/")[1]
        raw_b64 = data_url.split(",", 1)[1]
        img_bytes = base64.b64decode(raw_b64)
    except Exception as e:
        logger.warning(f"⚠️ data URL 解码失败: {e}")
        return None

    # 2. 拿 STS 凭证
    padded = token + "=" * (4 - len(token) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded))
    inner_token = payload.get("access_token", "")

    try:
        async with httpx.AsyncClient(timeout=30.0, trust_env=False) as c:
            sts_resp = await c.post(
                "https://www.insmind.com/api/tb-dam/asset/upload/tokens",
                json={"format": ext, "content_id": "", "dir": "", "device_id": "python-upload"},
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {inner_token}",
                    "x-product-type": "INDIVIDUAL_FREE",
                    "x-channel-id": "781",
                    "x-business-id": "124",
                    "x-device-id": "python-upload",
                    "origin": "https://www.insmind.com",
                    "referer": "https://www.insmind.com/creation",
                    "Cookie": f"token.prod={token}; token.org_id.prod={org_id}",
                },
            )
        if sts_resp.status_code != 200:
            logger.warning(f"⚠️ STS 失败: {sts_resp.status_code} {sts_resp.text[:100]}")
            return None
        sts = sts_resp.json()
    except Exception as e:
        logger.warning(f"⚠️ STS 请求异常: {e}")
        return None

    # 3. 构建 OSS 签名
    key = f'{sts["path"]}/{int(datetime.now(timezone.utc).timestamp() * 1000)}.{ext}'
    date_str = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    bucket = sts["bucket_name"]
    oss_hdr = f'x-oss-security-token:{sts["security_token"]}'
    string_to_sign = f"PUT\n\n{mime}\n{date_str}\n{oss_hdr}\n/{bucket}/{key}"
    sig = base64.b64encode(
        hmac.new(sts["access_key_secret"].encode(), string_to_sign.encode(), hashlib.sha1).digest()
    ).decode()
    auth = f'OSS {sts["access_key_id"]}:{sig}'
    import subprocess as _sp

    # 4. 写临时文件，用 curl.exe 上传（使用 STS 返回的区域域名，避免加速域名 DNS 劫持）
    # 优先使用 standby_endpoint 或 inner_endpoint 中的区域域名
    region_endpoint = sts.get("standby_endpoint", "") or sts.get("inner_endpoint", "")
    if region_endpoint:
        # 从 endpoint URL 中提取 hostname，如 https://oss-us-east-1.aliyuncs.com
        hostname = region_endpoint.replace("https://", "").replace("http://", "")
    else:
        # 回退到从 region 字段构建
        region = sts.get("region", "oss-us-east-1")
        hostname = f"{region}.aliyuncs.com"
    url = f"https://{bucket}.{hostname}/{key}"
    cdn_url = f'{sts["host"]}/{key}'
    logger.info(f"OSS 上传目标: {hostname}")


    tmp = tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False)
    try:
        tmp.write(img_bytes)
        tmp.close()

        result = await asyncio.to_thread(
            _sp.run,
            ["C:/Windows/System32/curl.exe",
             "-s", "--max-time", "30",
             "-w", "%{http_code}",
             "-X", "PUT",
             "-H", f"Content-Type: {mime}",
             "-H", f"Date: {date_str}",
             "-H", f"Authorization: {auth}",
             "-H", f"x-oss-security-token: {sts['security_token']}",
             "--data-binary", f"@{tmp.name}",
             "--insecure",
             url],
            capture_output=True, text=True, timeout=35)

        if result.stdout.strip() == "200":
            logger.info(f"✅ OSS 上传成功: {cdn_url}")
            return cdn_url
        else:
            logger.warning(f"OSS 上传失败: output=[{result.stdout[:100]}] stderr=[{result.stderr[:100]}]")
            return None
    except Exception as e:
        logger.warning(f"OSS 上传异常: {e!r}")
        import traceback
        logger.warning(f"Traceback: {traceback.format_exc()}")
        return None
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


# ============ 图生视频 ============


async def generate_image_to_video(
    *,
    email: str,
    token: str,
    user_id: str,
    org_id: str,
    credits: int = 0,
    image_data_urls: list[str],
    prompt: str,
    model: str = "Pixverse-V6.0",
    duration: int = 10,
    resolution: str = "360P",
    aspect_ratio: str = "16:9",
) -> InsMindResult:
    """
    图生视频：先压缩 → 上传 OSS(CDN) → 调 generations-image 端点
    支持多图（首帧+尾帧），逐张压缩+上传
    """
    # 1. 压缩+上传每张图片
    cdn_urls: list[str] = []
    for data_url in image_data_urls:
        if not data_url:
            continue
        img_url = _compress_image(data_url)
        if img_url.startswith("data:image/"):
            cdn_url = await _upload_to_oss(
                img_url, email, token, user_id, org_id
            )
            if cdn_url:
                cdn_urls.append(cdn_url)
                logger.info(f"📤 已上传到 CDN: {cdn_url[:60]}...")
            else:
                logger.warning("⚠️ OSS 上传失败，回退到 data URL（可能无法生成）")
                cdn_urls.append(img_url)
        else:
            cdn_urls.append(img_url)

    if not cdn_urls:
        return InsMindResult(code="failed", message="没有可用的图片")

    await sync_account_to_pool(email, token, user_id, credits, org_id)

    import os as _os3
    _saved3 = {k: _os3.environ.pop(k, None) for k in ['HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy','ALL_PROXY','all_proxy']}
    try:
        async with httpx.AsyncClient(timeout=300.0, trust_env=False) as c:
            resp = await c.post(
                f"{INSMIND2API_URL}/api/v1/videos/generations-image",
                json={
                    "prompt": prompt,
                    "model": model,
                    "duration": duration,
                    "resolution": resolution,
                    "aspect_ratio": aspect_ratio,
                    "image_urls": cdn_urls,
                    "account_email": email,
                },
            )
    except httpx.TimeoutException:
        return InsMindResult(code="failed", message="insmind2api 请求超时 (300s)")
    except Exception as e:
        return InsMindResult(code="failed", message=f"insmind2api 请求异常: {e}")

    if resp.status_code != 200:
        return InsMindResult(
            code="failed",
            message=f"insmind2api 返回 {resp.status_code}: {resp.text[:200]}",
        )

    # 图生视频：用自己的 SSE 文本提取
    data = resp.json()
    sse_text = ""
    raw_resp = (data or {}).get("response", "")
    if isinstance(raw_resp, str) and raw_resp:
        sse_text = _image_extract_sse(raw_resp)

    if sse_text:
        return InsMindResult(
            code="text_reply", message=sse_text,
            task_id=data.get("id", ""),
            raw_response=raw_resp,
        )

    return _parse_insmind_response(data)


# ============ 分发器（router 用） ============


async def generate_video(
    *,
    email: str,
    token: str,
    user_id: str,
    org_id: str,
    credits: int = 0,
    prompt: str,
    model: str = "Pixverse-V6.0",
    duration: int = 10,
    resolution: str = "360P",
    aspect_ratio: str = "16:9",
    input_images: Optional[list[str]] = None,
) -> InsMindResult:
    """根据有无图片自动分发文生/图生视频"""
    if input_images and input_images[0]:
        return await generate_image_to_video(
            email=email, token=token, user_id=user_id, org_id=org_id,
            credits=credits, prompt=prompt, model=model,
            duration=duration, resolution=resolution,
            aspect_ratio=aspect_ratio, image_data_urls=input_images,
        )
    return await generate_text_to_video(
        email=email, token=token, user_id=user_id, org_id=org_id,
        credits=credits, prompt=prompt, model=model,
        duration=duration, resolution=resolution,
        aspect_ratio=aspect_ratio,
    )