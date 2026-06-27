"""注册 → 浏览器内提交生成 → 检查 tenant 是否自动激活"""
import asyncio, json, base64, httpx
from patchright.async_api import async_playwright

BACKEND = "http://localhost:8005"

async def main():
    r = httpx.post(f"{BACKEND}/api/insmind/accounts/auto-register", timeout=180)
    data = r.json()
    if not data["success"]:
        print(f"FAIL: {data}"); return
    
    email = data["email"]
    tok = data["token"]
    print(f"OK: {email}")
    
    padded = tok + "=" * (4 - len(tok) % 4)
    d = json.loads(base64.urlsafe_b64decode(padded))
    inner = d["access_token"]
    parts = inner.split(".")
    p2 = parts[1] + "=" * (4 - len(parts[1]) % 4)
    sub = json.loads(base64.urlsafe_b64decode(p2))["sub"]
    
    async with async_playwright() as pw:
        b = await pw.chromium.launch(headless=True)
        ctx = await b.new_context()
        page = await ctx.new_page()
        
        await ctx.add_cookies([{
            "name": "token.prod", "value": tok,
            "domain": ".insmind.com", "path": "/",
        }])
        
        await page.goto("https://www.insmind.com/creation",
                        wait_until="networkidle", timeout=60000)
        
        # 从浏览器内提交 SSE 生成
        result = await page.evaluate(f"""
            async () => {{
                const payload = {{
                    content: {{
                        type: 'plain', scene_code: 'Pixversev60',
                        prompt: [{{type:'text', content:'test cat walking'}}],
                        parameters: {{ratio:'', resolution:'360P', duration:'5', styleCode:'Pixversev60'}},
                        duration: '5', resolution: '360P', text: 'test cat walking'
                    }},
                    name: 'user', role: 'user',
                    local_thread_id: 't-' + Date.now(),
                    local_message_id: 'm-' + Date.now(),
                    thread_id: '', attachments: [],
                    extra: {{prompt_suffix: '', enable_websearch: false}}
                }};
                try {{
                    const resp = await fetch('https://sse.insmind.com/api/ai-agent/v1/thread/completion', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json',
                            'Authorization': 'Bearer {inner}',
                            'x-user-id': '{sub}',
                            'x-product-type': 'INDIVIDUAL_FREE',
                            'x-channel-id': '781',
                            'origin': 'https://www.insmind.com',
                            'referer': 'https://www.insmind.com/creation',
                        }},
                        body: JSON.stringify(payload),
                    }});
                    const text = await resp.text();
                    return 'STATUS=' + resp.status + ' BODY=' + text.substring(0, 500);
                }} catch(e) {{
                    return 'ERROR=' + e.message;
                }}
            }}
        """)
        print(f"\n生成结果:\n  {result}")
        
        # 检查 cookies 是否有 org_id 了
        await page.wait_for_timeout(2000)
        new_cookies = await ctx.cookies()
        for c in new_cookies:
            if "org" in c["name"].lower():
                print(f"  org_cookie: {c['name']}={c['value'][:40]}")
        
        # 重新检查用户状态
        r2 = httpx.get("https://www.insmind.com/api/gaoding-art/v1/rewards/user/info",
            headers={
                "Authorization": f"Bearer {inner}",
                "x-user-id": str(sub),
                "x-product-type": "INDIVIDUAL_FREE",
                "x-channel-id": "781",
                "origin": "https://www.insmind.com",
            }, timeout=15)
        print(f"  用户状态: {r2.text[:200]}")
        
        await b.close()

asyncio.run(main())