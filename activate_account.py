#!/usr/bin/env python3
"""
insMind 账号激活 & 生成测试工具
用法:
  1. 在浏览器登录 insMind (https://www.insmind.com)
  2. 打开 DevTools → Application → Cookies → token.prod 的值
  3. 运行: python activate_account.py <token.prod>
  
脚本会自动:
  - 注入 cookie 访问 creation 激活 tenant
  - 抓取 org_id
  - 写入 insmind2api 池
  - 测试视频生成
"""
import asyncio, json, sys, base64, httpx, logging, os
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("activate")

INSMIND2API = "http://127.0.0.1:5105"
BACKEND = "http://localhost:8005"
POOL_FILE = Path(__file__).parent / "configs" / "accounts.json"

def decode_token(raw: str) -> dict:
    padded = raw + "=" * (4 - len(raw) % 4)
    d = json.loads(base64.urlsafe_b64decode(padded))
    uid = ""
    at = d.get("access_token", "")
    if at and "." in at:
        p = at.split(".")[1] + "=" * (4 - len(at.split(".")[1]) % 4)
        uid = str(json.loads(base64.urlsafe_b64decode(p)).get("sub", ""))
    return {"access_token": at, "user_id": uid, "raw": d}

async def activate_and_test(token_prod: str, email: str = ""):
    decoded = decode_token(token_prod)
    logger.info(f"access_token: {decoded['access_token'][:30]}...")
    logger.info(f"user_id: {decoded['user_id']}")

    # ── 第一步：Playwright 激活 tenant ──
    from patchright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True,
            args=["--headless=new", "--no-sandbox", "--disable-gpu"])
        ctx = await browser.new_context()
        page = await ctx.new_page()

        # 注入 token cookie
        await ctx.add_cookies([{
            "name": "token.prod",
            "value": token_prod,
            "domain": ".insmind.com",
            "path": "/",
        }])

        logger.info("访问 creation 页面激活 tenant...")
        await page.goto("https://www.insmind.com/creation",
                        wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(10000)  # 等 JS 设 cookie

        # 抓 org_id
        org_id = None
        cookies = await ctx.cookies()
        for c in cookies:
            if "org_id" in c["name"]:
                org_id = c["value"]
                logger.info(f"✅ 已激活租户, org_id={org_id[:30]}...")
                break

        if not org_id:
            # 再试一次 - 调 API 触发 lazy creation
            inner = decoded["access_token"]
            uid = decoded["user_id"]
            result = await page.evaluate(f"""async () => {{
                try {{
                    const r = await fetch('https://www.insmind.com/api/gaoding-art/v1/rewards/user/info', {{
                        headers:{{'Authorization':'Bearer {inner}','x-user-id':'{uid}',
                            'x-product-type':'INDIVIDUAL_FREE','x-channel-id':'781'}}
                    }});
                    return await r.text().then(t => t.substring(0,300));
                }} catch(e) {{ return 'ERR:' + e.message; }}
            }}""")
            logger.info(f"rewards API: {result[:100]}")
            await page.wait_for_timeout(3000)

            cookies = await ctx.cookies()
            for c in cookies:
                if "org_id" in c["name"]:
                    org_id = c["value"]
                    logger.info(f"✅ 已激活租户(API触发), org_id={org_id[:30]}...")
                    break

        if not org_id:
            logger.error("❌ 无法获取 org_id，tenant 激活失败")
            await browser.close()
            return False

        await browser.close()

    # ── 第二步：写入池 ──
    pool_entry = {
        "email": email or f"manual-{org_id[-8:]}@activated.com",
        "token": token_prod,
        "userId": decoded["user_id"],
        "credits": 0,
        "orgId": org_id,
    }

    POOL_FILE.parent.mkdir(parents=True, exist_ok=True)
    pool = []
    if POOL_FILE.exists():
        with open(POOL_FILE) as f:
            try: pool = json.load(f)
            except: pass
    pool.append(pool_entry)
    with open(POOL_FILE, "w") as f:
        json.dump(pool, f, indent=2)
    logger.info(f"✅ 已写入池，共 {len(pool)} 个")

    # 同步到 insmind2api 运行时
    async with httpx.AsyncClient(timeout=10) as c:
        await c.post(f"{INSMIND2API}/api/accounts/sync",
            json={"accounts": [{"email": pool_entry["email"], "token": token_prod,
                "userId": decoded["user_id"], "credits": 0, "orgId": org_id}]})

    # ── 第三步：测试视频生成 ──
    logger.info("测试视频生成...")
    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(f"{INSMIND2API}/api/v1/videos/generations", json={
            "prompt": "A cute cat walking on grass",
            "model": "Pixverse-V6.0", "duration": 5, "resolution": "360P",
        })
        if r.status_code == 200:
            data = r.json()
            vu = data.get("video_url")
            if vu:
                logger.info(f"✅ 生成成功! 视频URL: {vu}")
            else:
                logger.info(f"status={data.get('status')}, 无video_url(rewards API可能触发过慢)")
        else:
            logger.error(f"❌ 生成失败: {r.status_code} {r.text[:200]}")

    logger.info("✅ 完成")
    return True

async def main():
    token = ""
    email = ""
    if len(sys.argv) >= 2 and sys.argv[1] == "--file":
        # 从文件读 token
        with open(sys.argv[2]) as f:
            token = f.read().strip()
        email = sys.argv[3] if len(sys.argv) > 3 else ""
    else:
        token = sys.argv[1] if len(sys.argv) >= 2 else ""
        email = sys.argv[2] if len(sys.argv) > 2 else ""

    if not token:
        print(__doc__)
        sys.exit(1)
    ok = await activate_and_test(token, email)
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    asyncio.run(main())
