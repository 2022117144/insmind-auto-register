"""
注册 + 补全 first login 流程 + 检查 tenant
"""
import asyncio, json, base64, httpx

BACKEND = "http://localhost:8005"
INSMIND2API = "http://127.0.0.1:5105"

async def main():
    from patchright.async_api import async_playwright
    
    print("=== auto_register ===")
    r = httpx.post(f"{BACKEND}/api/insmind/accounts/auto-register", timeout=180)
    data = r.json()
    if not data.get("success"):
        print(f"FAIL: {data}")
        return
    
    email = data["email"]
    tok = data["token"]
    print(f"OK: {email}")
    
    padded = tok + "=" * (4 - len(tok) % 4)
    d = json.loads(base64.urlsafe_b64decode(padded))
    inner = d["access_token"]
    parts = inner.split(".")
    p2 = parts[1] + "=" * (4 - len(parts[1]) % 4)
    uid = json.loads(base64.urlsafe_b64decode(p2))["sub"]
    print(f"uid={uid}")
    
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context()
        page = await ctx.new_page()
        
        await ctx.add_cookies([{
            "name": "token.prod", "value": tok,
            "domain": ".insmind.com", "path": "/",
        }])
        
        await page.goto("https://www.insmind.com/creation",
                        wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)
        
        url = page.url
        title = await page.title()
        print(f"url={url} title={title}")
        
        cookies = await ctx.cookies()
        for c in cookies:
            if "org" in c["name"].lower():
                print(f"org_cookie: {c['name']}={c['value'][:40]}")
        
        body = await page.evaluate("document.body.innerText.substring(0,4000)")
        print(f"\n--- body text ---\n{body}\n---")
        
        await b.close()
    
    print("\n=== user status ===")
    r2 = httpx.get("https://www.insmind.com/api/gaoding-art/v1/rewards/user/info",
        headers={
            "Authorization": f"Bearer {inner}",
            "x-user-id": str(uid),
            "x-product-type": "INDIVIDUAL_FREE",
            "x-channel-id": "781",
            "origin": "https://www.insmind.com",
        }, timeout=15)
    print(r2.text[:300])

asyncio.run(main())