"""
insMind OSS 上传工具 — 用 curl.exe 绕过 Python SSL 兼容性问题
"""

import json, base64, hashlib, hmac, subprocess, tempfile, os, logging
from datetime import timezone, datetime
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


async def upload_to_oss(
    image_bytes: bytes,
    content_type: str = "image/jpeg",
) -> Optional[str]:
    """
    上传图片到 insMind OSS，返回 CDN URL。
    通过 curl.exe 上传以规避 Python SSL 栈的兼容问题。
    """
    from app.services.insmind_gen import _get_account_sts

    sts = await _get_account_sts()
    if not sts:
        logger.error("无法获取 STS 凭证")
        return None

    key = f'{sts["path"]}/{int(datetime.now().timestamp() * 1000)}.jpg'
    date_str = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    bucket = sts["bucket_name"]

    # OSS v3 签名
    oss_hdr = f'x-oss-security-token:{sts["security_token"]}'
    string_to_sign = f"PUT\n\n{content_type}\n{date_str}\n{oss_hdr}\n/{bucket}/{key}"
    sig = base64.b64encode(
        hmac.new(
            sts["access_key_secret"].encode(),
            string_to_sign.encode(),
            hashlib.sha1,
        ).digest()
    ).decode()
    auth = f'OSS {sts["access_key_id"]}:{sig}'

    url = f'https://oss-accelerate.aliyuncs.com/{bucket}/{key}'
    cdn_url = f'{sts["host"]}/{key}'

    # 写临时文件
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp.write(image_bytes)
    tmp.close()

    try:
        proc = await asyncio.create_subprocess_exec(
            "curl.exe",
            "-s", "--max-time", "30",
            "-x", "http://127.0.0.1:7897",
            "-X", "PUT",
            "-H", f"Content-Type: {content_type}",
            "-H", f"Date: {date_str}",
            "-H", f"Authorization: {auth}",
            "-H", f"x-oss-security-token: {sts['security_token']}",
            "--data-binary", f"@{tmp.name}",
            "--insecure",
            url,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=35)
        output = stdout.decode() if stdout else ""

        if "200 OK" in output or "200" in output.split("\n")[0]:
            logger.info(f"✅ OSS 上传成功: {cdn_url}")
            return cdn_url
        else:
            logger.warning(f"OSS 上传失败: {output[:200]}")
            return None
    except Exception as e:
        logger.warning(f"OSS 上传异常: {e}")
        return None
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass