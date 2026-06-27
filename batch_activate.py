"""从 DB 读取未激活账号，逐个激活 tenant"""
import asyncio, json, httpx, logging, sys
from pathlib import Path

sys.path.insert(0, "E:/视频生成/dreamina-auto-register-main")
from activate_account import activate_and_test

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("batch_activate")

BACKEND = "http://localhost:8005"

async def main():
    # 1. 从 DB 拿所有账号
    r = httpx.get(f"{BACKEND}/api/insmind/accounts", timeout=10)
    accounts = r.json()
    logger.info(f"DB 共 {len(accounts)} 个账号")

    activated = 0
    for a in accounts:
        email = a["email"]
        oid = a.get("org_id", "") or ""
        tok = a.get("token", "")
        if oid:
            logger.info(f"  ⏭️ {email} 已有 org_id，跳过")
            continue
        if not tok:
            logger.info(f"  ⏭️ {email} 无 token，跳过")
            continue

        logger.info(f"  🔄 激活 {email}...")
        ok = await activate_and_test(tok, email)
        if ok:
            activated += 1
            # 更新 DB 中的 org_id（脚本内部已写入池，但需同步 DB）
            # 从池文件读取最新 orgId
            pool_file = Path("E:/视频生成/dreamina-auto-register-main/insmind2api/configs/accounts.json")
            if pool_file.exists():
                with open(pool_file) as f:
                    pool = json.load(f)
                for p in pool:
                    if p.get("email") == email and p.get("orgId"):
                        # 更新 DB
                        r2 = httpx.patch(f"{BACKEND}/api/insmind/accounts/{a['id']}/token",
                            json={"token": tok}, timeout=10)
                        logger.info(f"    DB 更新: {r2.status_code}")
                        break
        else:
            logger.error(f"  ❌ {email} 激活失败")

    logger.info(f"完成: {activated} 个已激活")

asyncio.run(main())