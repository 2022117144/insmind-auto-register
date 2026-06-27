"""检查所有 cookies"""
import asyncio, sys, json
sys.path.insert(0, ".")
import httpx

async def main():
    r = httpx.get("http://localhost:8005/api/insmind/accounts", timeout=10)
    a = r.json()[0]
    tok = a['token']

    from patchright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        ctx = await b.new_context()
        page = await ctx.new_page()
        await ctx.add_cookies([{"name": "token.prod", "value": tok,
            "domain": ".insmind.com", "path": "/"}])
        resp = await page.goto("https://www.insmind.com/creation", timeout=60000)
        print(f"status={resp.status if resp else 'none'}")
        await page.wait_for_timeout(5000)
        
        cookies = await ctx.cookies()
        print(f"\n共 {len(cookies)} 个 cookies:")
        for c in cookies:
            print(f"  {c['name']}: {c['value'][:40]}... (domain={c['domain']})")
        
        print(f"\n标题: {await page.title()}")
        print(f"URL: {page.url}")
        await b.close()

asyncio.run(main())
print("DONE")