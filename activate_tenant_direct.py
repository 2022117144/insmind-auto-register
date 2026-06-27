"""从池拿账号注入 cookie 激活 tenant"""
import asyncio, json, base64, httpx
from patchright.async_api import async_playwright

async def activate():
    # 拿新号 token（直接从配置文件里读）
    import os, sys
    pool_file = r"E:\视频生成\dreamina-auto-register-main\insmind2api\configs\accounts.json"
    with open(pool_file) as f:
        accounts = json.load(f)
    
    if not accounts:
        print("❌ 池子为空")
        return
    
    a = accounts[-1]  # 拿最新的
    tok = a['token']
    email = a['email']
    print(f"激活: {email}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True,
            args=["--headless=new", "--no-sandbox", "--disable-gpu"])
        ctx = await browser.new_context()
        page = await ctx.new_page()
        
        await ctx.add_cookies([{
            "name": "token.prod",
            "value": tok,
            "domain": ".insmind.com",
            "path": "/",
        }])
        
        print("访问 creation 页面...")
        await page.goto("https://www.insmind.com/creation", wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(8000)
        
        cookies = await ctx.cookies()
        for c in cookies:
            if "org_id" in c["name"]:
                a["orgId"] = c["value"]
                print(f"✅ 已激活租户, org_id={c['value'][:30]}...")
                break
        
        if not a.get("orgId"):
            print("⚠️ 未获取到 org_id")
        
        # 保存回池
        with open(pool_file, 'w') as f:
            json.dump(accounts, f, indent=2)
        print("✅ org_id 已保存到池")
        
        await browser.close()

asyncio.run(activate())