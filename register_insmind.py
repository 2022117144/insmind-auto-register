#!/usr/bin/env python3
"""
insMind 自动注册 — 全后台版
mail.tm API 邮箱 + Playwright headless SSO 登录 + SVG CAPTCHA OCR + 自动入库
"""

import asyncio, re, json, logging, sys, os, argparse, base64, random, string
from typing import Optional, Tuple

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("insmind")

TEMPMAIL_API = "https://api.tempmail.ing"
INSMIND2API_URL = "http://127.0.0.1:5105"
POLL_INTERVAL = 3
POLL_TIMEOUT = 120
PROXY = "http://127.0.0.1:7897"


async def create_mail() -> Tuple[str, str]:
    """获取临时邮箱（tempmail.ing API，不走代理，无需鉴权）"""
    import httpx as _httpx
    import os as _os
    _saved = {k: _os.environ.pop(k, None) for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]}
    try:
        async with _httpx.AsyncClient(timeout=15.0) as c:
            r = await c.post(f"{TEMPMAIL_API}/api/generate", json={"duration": 10})
            if r.status_code == 200:
                data = r.json()
                if data.get("success"):
                    addr = data["email"]["address"]
                    logger.info(f"邮箱: {addr}")
                    return addr, addr
            logger.warning(f"tempmail.ing 创建失败: {r.status_code} {r.text[:200]}")
            raise Exception("无法获取邮箱")
    except Exception as e:
        logger.warning(f"tempmail.ing API 失败: {e}")
        raise Exception("无法获取邮箱")
    finally:
        for k, v in _saved.items():
            if v is not None:
                _os.environ[k] = v


# 通过 httpx 获取验证码时不走代理（直连云 API）
async def poll_code(email: str, _mail_token: str = "") -> Optional[str]:
    """轮询 tempmail.ing API 获取验证码"""
    import os as _os
    _saved = {k: _os.environ.pop(k, None) for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]}
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            start = asyncio.get_event_loop().time()
            while (asyncio.get_event_loop().time() - start) < POLL_TIMEOUT:
                try:
                    r = await c.get(f"{TEMPMAIL_API}/api/emails/{email}")
                    if r.status_code == 200:
                        data = r.json()
                        if data.get("success"):
                            for msg in data.get("emails", []):
                                subj = msg.get("subject", "")
                                body = (msg.get("text", "") or msg.get("content", "") or "")
                                from_addr = msg.get("from_address", "")
                                if "insmind" in from_addr.lower() or "insmind" in subj.lower():
                                    if "verify" in subj.lower() or "验证" in subj:
                                        m = re.search(r"(\d{6})", body)
                                        if m:
                                            logger.info(f"验证码: {m.group(1)}")
                                            return m.group(1)
                except Exception:
                    pass
                await asyncio.sleep(POLL_INTERVAL)
        return None
    finally:
        for k, v in _saved.items():
            if v is not None:
                _os.environ[k] = v


def decode_token(raw: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """解码 token.prod，返回 (access_token, user_id, refresh_token)"""
    try:
        padded = raw + "=" * (4 - len(raw) % 4)
        d = json.loads(base64.urlsafe_b64decode(padded))
        at = d.get("access_token")
        rt = d.get("refresh_token") or None  # None if empty string
        uid = None
        if at and '.' in at:
            p = at.split(".")[1] + "=" * (4 - len(at.split(".")[1]) % 4)
            uid = str(json.loads(base64.urlsafe_b64decode(p)).get("sub", ""))
        return at, uid, rt
    except Exception as e:
        logger.error(f"解码失败: {e}")
        return None, None, None


async def register() -> dict:
    """Playwright 全后台注册"""
    from patchright.async_api import async_playwright

    email, mail_token = await create_mail()
    result = {"success": False, "email": email, "token": None, "access_token": None, "userId": None, "error": None}
    logger.info(f"邮箱: {email}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True,
            args=["--headless=new", "--no-sandbox", "--disable-gpu", "--no-proxy-server"])
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = await ctx.new_page()

        try:
            await page.goto("https://ums.insmind.com/ums/cgi/sso?login_type=popup")
            await page.wait_for_timeout(2000)
            await page.locator('button:has-text("Continue with email")').first.wait_for(timeout=15000)
            await page.locator('button:has-text("Continue with email")').first.click()
            await page.wait_for_timeout(2000)
            await page.locator('input[placeholder*="email"]').first.fill(email)
            await page.wait_for_timeout(500)

            ev = page.locator('button:has-text("Email verification")')
            if await ev.count() > 0:
                await ev.first.click()
                await page.wait_for_timeout(1500)

            await page.locator('button:has-text("Send code")').first.click()
            await page.wait_for_timeout(1500)

            # CAPTCHA 处理（使用云打码 jfbym.com）
            JFBYM_TOKEN = "sLchUssAXpcRZSyMUBlFdx-xkTNXw8LRb6-hYkm7m_4"
            JFBYM_URL = "http://api.jfbym.com/api/YmServer/customApi"
            import httpx as _httpx_for_captcha

            for attempt in range(8):
                if await page.locator("gdwc-modal-capcha").count() == 0:
                    break
                logger.info(f"CAPTCHA 第 {attempt+1} 次尝试")

                # 获取 SVG 位置并截图（2x 缩放提高精度）
                rect = await page.evaluate("""() => {
                    const el = document.querySelector('gdwc-modal-capcha');
                    const svg = el?.shadowRoot?.querySelector('svg');
                    if (!svg) return null;
                    const r = svg.getBoundingClientRect();
                    return {x: r.x, y: r.y, w: r.width, h: r.height};
                }""")

                if rect and rect['w'] > 0:
                    # 4x 放大 SVG
                    await page.evaluate("""() => {
                        const el = document.querySelector('gdwc-modal-capcha');
                        const svg = el?.shadowRoot?.querySelector('svg');
                        if (!svg) return;
                        svg.style.transform = 'scale(6)';
                        svg.style.transformOrigin = 'top left';
                    }""")
                    await page.wait_for_timeout(200)

                    # 获取缩放后的 SVG 位置（可能有 shadow DOM 渲染延迟）
                    svg_rect = await page.evaluate("""() => {
                        const el = document.querySelector('gdwc-modal-capcha');
                        const svg = el?.shadowRoot?.querySelector('svg');
                        if (!svg) return null;
                        const r = svg.getBoundingClientRect();
                        if (!r || !r.width || r.width <= 0) return null;
                        return {x: r.x, y: r.y, w: r.width, h: r.height};
                    }""")
                    # 回退：SVG rect 无效时用 CAPTCHA 组件本身的 rect
                    if not svg_rect:
                        svg_rect = rect
                    try:
                        clip_obj = {
                            "x": float(svg_rect["x"]),
                            "y": float(svg_rect["y"]),
                            "width": float(svg_rect["w"]),
                            "height": float(svg_rect["h"]),
                        }
                        clip = await page.screenshot(clip=clip_obj)
                    except Exception as e:
                        logger.warning(f"CAPTCHA 截图失败: {e}, 尝试全页截图")
                        clip = await page.screenshot()
                    # 用云打码识别
                    import base64 as _b64
                    b64_img = _b64.b64encode(clip).decode()
                    async with _httpx_for_captcha.AsyncClient(timeout=30) as _jc:
                        _jr = await _jc.post(JFBYM_URL, json={
                            "image": b64_img,
                            "token": JFBYM_TOKEN,
                            "type": "10110",
                        })
                        _jd = _jr.json()
                    code = _jd.get("data", {}).get("data", "") if _jd.get("code") == 10000 else ""
                    logger.info(f"云码: {code if code else '识别失败'}")
                    if not code:
                        await page.wait_for_timeout(1000)
                    # 恢复SVG大小
                    await page.evaluate("""() => {
                        const el = document.querySelector('gdwc-modal-capcha');
                        const svg = el?.shadowRoot?.querySelector('svg');
                        if (!svg) return;
                        svg.style.transform = '';
                    }""")
                    if code and len(code) >= 2:
                        # 只接受纯英数字验证码，跳过乱码
                        import re as re_check
                        if not re_check.match(r'^[a-zA-Z0-9\-_]{2,8}$', code.strip()):
                            logger.info(f"OCR 乱码跳过: {code}")
                            # 换一个
                            ch = page.locator("button:has-text('Change one')")
                            if await ch.count() > 0:
                                await ch.first.click()
                                await page.wait_for_timeout(1500)
                            continue
                        logger.info(f"OCR: {code}")
                        inp = page.locator("gdwc-modal-capcha input")
                        if await inp.count() == 0:
                            inp = page.locator("input[placeholder*='Fill in']")
                        await inp.first.fill(code)
                        await page.wait_for_timeout(500)
                        sb = page.locator("gdwc-modal-capcha button:has-text('Submit')")
                        if await sb.count() > 0:
                            await sb.first.click()
                            await page.wait_for_timeout(2000)
                            # 验证 CAPTCHA 是否真的关闭了
                            if await page.locator("gdwc-modal-capcha").count() == 0:
                                logger.info("CAPTCHA 验证通过")
                                # 重新点 Send code（CAPTCHA 通过后可能需要）
                                sc = page.locator('button:has-text("Send code")')
                                if await sc.count() > 0:
                                    await sc.first.click()
                                    await page.wait_for_timeout(1500)
                                break
                            else:
                                logger.info("CAPTCHA 验证失败，重试")

                # 点 Change one 换一个
                ch = page.locator("button:has-text('Change one')")
                if await ch.count() > 0:
                    await ch.first.click()
                    await page.wait_for_timeout(1500)

            # 轮询验证码
            logger.info("等待验证码...")
            code = await poll_code(email, mail_token)
            if not code:
                result["error"] = "验证码超时"
                return result
            logger.info(f"验证码: {code}")

            # 填验证码
            ci = page.locator('input[placeholder*="code"]')
            if await ci.count() == 0:
                ci = page.locator("input:visible").last
            await ci.first.fill(code)

            # 点 Log In
            await page.locator('button:has-text("Log In")').first.wait_for(timeout=10000)
            await page.locator('button:has-text("Log In")').first.click()
            await page.wait_for_timeout(5000)

            # 提取 token — 从 SSO popup 的 cookies 中获取
            logger.info("=== 所有 Cookie ===")
            for c in await ctx.cookies():
                n, v = c["name"], c["value"][:40]
                logger.info(f"  {n}: {v}...")
                if c["name"] == "token.prod":
                    result["token"] = c["value"]
                    at, uid, rt = decode_token(c["value"])
                    result["access_token"] = at
                    result["userId"] = uid
                    if not result.get("refresh_token"):
                        result["refresh_token"] = rt or ""
                    result["success"] = True
                elif c["name"] == "token.prod.refresh_token":
                    result["refresh_token"] = c["value"]
            logger.info("=== 结束 ===")
            if result["success"]:
                if result.get("refresh_token"):
                    logger.info(f"注册成功: {email}, refresh_token: {result['refresh_token'][:30]}...")
                else:
                    logger.warning(f"⚠️ insMind 未发放 refresh_token（email 注册通常不发），账号将在 8h 后过期")

            # 激活租户：跟着 SSO 登录的重定向走，让 www.insmind.com 自动创建 tenant
            if result["success"] and result.get("token"):
                try:
                    # 等待 SSO popup 完成重定向到 www.insmind.com
                    await page.wait_for_timeout(3000)
                    current_url = page.url
                    logger.info(f"SSO 重定向后 URL: {current_url}")

                    # 新页面可能没有 SSO 的 cookie，显式注入
                    await ctx.add_cookies([{
                        "name": "token.prod",
                        "value": result["token"],
                        "domain": ".insmind.com",
                        "path": "/",
                    }])

                    # 在新页面访问 creation 激活 tenant（domcontentloaded + 等待 cookie 设置）
                    create_page = await ctx.new_page()
                    await create_page.goto("https://www.insmind.com/creation",
                                           wait_until="domcontentloaded", timeout=60000)
                    await create_page.wait_for_timeout(10000)
                    await create_page.close()

                    # 收集所有 cookie 找 org_id
                    cookies = await ctx.cookies()
                    for c in cookies:
                        if "org_id" in c["name"]:
                            result["org_id"] = c["value"]
                            logger.info(f"已激活租户, org_id={c['value'][:30]}...")
                            break

                    if not result.get("org_id"):
                        logger.info("首次未获取到 org_id，等待 10s 后重试...")
                        await page.wait_for_timeout(10000)
                        cookies = await ctx.cookies()
                        for c in cookies:
                            if "org_id" in c["name"]:
                                result["org_id"] = c["value"]
                                logger.info(f"已激活租户(重试), org_id={c['value'][:30]}...")
                                break

                    if not result.get("org_id"):
                        logger.warning("⚠️ 访问 creation 后未获取到 org_id cookie")
                except Exception as e:
                    logger.warning(f"激活租户过程异常（不影响注册）: {e}")

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"失败: {e}")
        finally:
            await ctx.close()
            await browser.close()
    return result


async def add_to_pool(email: str, token: str, userId: str, refresh_token: str = "", org_id: str = "") -> bool:
    """把注册结果写入 insmind2api 账号池"""
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.get(f"{INSMIND2API_URL}/api/accounts")
        data = r.json()
        cur = data if isinstance(data, list) else data.get("accounts", []) if r.status_code == 200 else []
    async with httpx.AsyncClient(timeout=10.0) as c:
        entry = {"email": email, "token": token, "userId": userId or "0", "credits": 0, "refreshToken": refresh_token}
        if org_id:
            entry["orgId"] = org_id
        r = await c.post(f"{INSMIND2API_URL}/api/accounts/sync",
            json={"accounts": cur + [entry]})
        if r.status_code == 200:
            logger.info(f"已加入池，同步成功")
            return True
    return False


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto-add", action="store_true")
    args = parser.parse_args()
    logger.info("=== insMind 自动注册 ===")
    result = await register()
    print("\n--- RESULT ---")
    print(json.dumps({k: v for k, v in result.items()}, separators=(",", ":"), ensure_ascii=False))
    sys.stdout.flush()
    if result["success"] and args.auto_add and result["token"] and result.get("org_id"):
        await add_to_pool(result["email"], result["token"], result["userId"] or "", result.get("refresh_token", ""), result.get("org_id", ""))
        # 同步写入后端 DB（前端从 DB 读）
        try:
            async with httpx.AsyncClient(timeout=10) as _c:
                _r = await _c.post(f"http://localhost:8005/api/insmind/accounts", json={
                    "email": result["email"],
                    "token": result["token"],
                    "user_id": result.get("userId", ""),
                    "refresh_token": result.get("refresh_token", ""),
                    "org_id": result.get("org_id", ""),
                    "credits": 0,
                })
                if _r.status_code in (201, 409):
                    logger.info("✅ 已写入后端 DB")
                else:
                    logger.warning(f"⚠️ 写入后端 DB 返回 {_r.status_code}: {_r.text[:100]}")
        except Exception as _e:
            logger.warning(f"⚠️ 写入后端 DB 失败: {_e}")
    sys.exit(0 if result["success"] else 1)

if __name__ == "__main__":
    asyncio.run(main())
