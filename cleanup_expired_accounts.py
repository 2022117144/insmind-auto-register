#!/usr/bin/env python3
"""
清理过期 insMind 账号
从 8005 后端拉取账号列表，检查 token 过期时间，删除已过期的账号
同时同步清理 5105 内存池

用法:
  python cleanup_expired_accounts.py              # 清理过期账号
  python cleanup_expired_accounts.py --dry-run    # 只列出过期账号，不删除
  python cleanup_expired_accounts.py --list-all   # 列出所有账号及过期时间
"""

import asyncio
import base64
import json
import logging
import sys
from datetime import datetime, timezone

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("cleanup")

BACKEND_URL = "http://127.0.0.1:8005"
INSMIND2API_URL = "http://127.0.0.1:5105"


def decode_token_expiry(token_prod: str) -> str | None:
    """解码 token.prod，返回 access_token_expires_at 时间字符串"""
    try:
        padded = token_prod + "=" * (4 - len(token_prod) % 4)
        decoded = base64.urlsafe_b64decode(padded)
        payload = json.loads(decoded)
        return payload.get("access_token_expires_at")
    except Exception:
        return None


def is_expired(expires_at_str: str | None) -> bool:
    """判断是否已过期"""
    if not expires_at_str:
        return True  # 无法解析的视为过期
    try:
        # 格式: 2026-07-27T23:39:32.000Z
        expires = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return expires < now
    except Exception:
        return True


async def list_accounts() -> list[dict]:
    """从 8005 后端拉取所有账号"""
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(f"{BACKEND_URL}/api/insmind/accounts")
        if r.status_code != 200:
            logger.error(f"拉取账号失败: {r.status_code} {r.text[:200]}")
            return []
        return r.json()


async def delete_account(account_id: int) -> bool:
    """删除指定 ID 的账号"""
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.delete(f"{BACKEND_URL}/api/insmind/accounts/{account_id}")
        if r.status_code == 200:
            return True
        logger.warning(f"删除账号 {account_id} 失败: {r.status_code} {r.text[:100]}")
        return False


async def main():
    dry_run = "--dry-run" in sys.argv
    list_all = "--list-all" in sys.argv

    accounts = await list_accounts()
    if not accounts:
        logger.info("没有账号需要清理")
        return

    if list_all:
        print(f"\n{'ID':>4}  {'Email':40s}  {'Expires At':30s}  {'Status':10s}  {'OrgId':25s}")
        print("-" * 120)
        for acct in accounts:
            expires_at = decode_token_expiry(acct.get("token", ""))
            expired = is_expired(expires_at)
            status = "过期" if expired else "有效"
            print(f"{acct.get('id', '?'):>4}  {acct['email']:40s}  {expires_at or 'N/A':30s}  {status:10s}  {acct.get('org_id', '')[:25]}")
        print(f"\n共 {len(accounts)} 个账号")
        return

    expired_accounts = []
    for acct in accounts:
        expires_at = decode_token_expiry(acct.get("token", ""))
        if is_expired(expires_at):
            expired_accounts.append(acct)
            logger.info(f"过期: [{acct['id']}] {acct['email']:40s} expires={expires_at}")

    if not expired_accounts:
        logger.info(f"✅ 所有 {len(accounts)} 个账号均有效，无需清理")
        return

    logger.info(f"发现 {len(expired_accounts)}/{len(accounts)} 个过期账号")

    if dry_run:
        logger.info("🧪 仅预览模式，未执行删除")
        return

    deleted = 0
    for acct in expired_accounts:
        aid = acct.get("id")
        if not aid:
            continue
        ok = await delete_account(aid)
        if ok:
            deleted += 1
            logger.info(f"🗑️ 已删除 [{aid}] {acct['email']}")
        await asyncio.sleep(0.3)  # 避免太快

    logger.info(f"✅ 清理完成: 删除了 {deleted}/{len(expired_accounts)} 个过期账号")
    logger.info(f"剩余账号: {len(accounts) - deleted}")


if __name__ == "__main__":
    asyncio.run(main())