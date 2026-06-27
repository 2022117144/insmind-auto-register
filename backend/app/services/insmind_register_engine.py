"""insMind Auto Register - 注册引擎（核心流程编排）"""

import asyncio
import logging
import re
import json
from datetime import datetime
from typing import Optional, Dict, Any
from urllib.parse import urljoin

from patchright.async_api import async_playwright, Page, BrowserContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.core.config import settings
from app.models.insmind_account import InsMindAccount
from app.models.proxy_node import ProxyNode
from app.services.browser_stealth import BrowserStealth
from app.services.human_behavior import HumanBehavior
from app.services.temp_mail_client import temp_mail_client
from app.services.clash_manager import clash_manager

logger = logging.getLogger(__name__)


class TaskInterruptedError(Exception):
    """任务被用户手动暂停或取消"""
    pass


class TokenExtractor:
    """insMind Token 多路提取器"""

    COOKIE_NAMES = ["token", "access_token", "session", "auth", "sid", "connect.sid"]
    STORAGE_KEYS = ["token", "accessToken", "userToken", "sessionId", "authToken"]

    def __init__(self, page: Page, context: BrowserContext):
        self.page = page
        self.context = context

    async def extract_all(self) -> Dict[str, Any]:
        """执行所有提取方法"""
        result = {
            "token": None,
            "all_tokens": {},
            "cookies": [],
        }

        # 1. Cookie 提取
        cookies = await self.context.cookies()
        result["cookies"] = cookies
        for cookie in cookies:
            name = cookie.get("name", "")
            if any(sn in name.lower() for sn in self.COOKIE_NAMES):
                result["all_tokens"][f"cookie_{name}"] = cookie["value"]
                if not result["token"]:
                    result["token"] = cookie["value"]

        # 2. LocalStorage 提取
        try:
            ls = await self.page.evaluate("""() => {
                const items = {};
                for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);
                    items[key] = localStorage.getItem(key);
                }
                return items;
            }""")
            for key in self.STORAGE_KEYS:
                if key in ls:
                    result["all_tokens"][f"ls_{key}"] = ls[key]
                    if not result["token"]:
                        result["token"] = ls[key]
        except Exception as e:
            logger.debug(f"LocalStorage 提取失败: {e}")

        return result


class InsMindRegisterEngine:
    """insMind 注册引擎"""

    # 页面选择器（基于实测验证）
    SELECTORS = {
        "login_button": [
            'button:has-text("Log in/Sign up")',
            ':text-is("Log in/Sign up")',
            '[class*="login"]:has-text("Sign up")',
        ],
        "continue_email": [
            'button:has-text("Continue with email")',
            ':text-is("Continue with email")',
        ],
        "email_input": [
            'input[type="email"]',
            'input[name="email"]',
            'input[placeholder*="email" i]',
            "input:not([type])",
        ],
        "email_password_login": [
            'button:has-text("Email verification")',
            ':text-is("Email verification")',
        ],
        "verification_code_input": [
            'input[placeholder*="verification" i]',
            'input[placeholder*="code" i]',
            'input[maxlength="6"]',
        ],
        "send_code": [
            'button:has-text("Send code")',
        ],
        "login_submit": [
            'button:has-text("Log In")',
            'button[type="submit"]',
        ],
        "current_email_display": [
            '[class*="email"]',
        ],
    }

    def __init__(self):
        self.playwright = None
        self.browser_stealth: Optional[BrowserStealth] = None

    async def initialize(self):
        """初始化引擎"""
        self.playwright = await async_playwright().start()
        self.browser_stealth = BrowserStealth(self.playwright)

    async def shutdown(self):
        """关闭引擎"""
        if self.browser_stealth:
            try:
                await self.browser_stealth.close()
            except Exception:
                pass
            self.browser_stealth = None
        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception:
                pass
            self.playwright = None
        await temp_mail_client.close()

    async def _find_element(self, page: Page, selector_key: str, timeout: int = 10000):
        """多选择器并发匹配"""
        selectors = self.SELECTORS.get(selector_key, [])
        if not selectors:
            return None
        combined = page.locator(selectors[0])
        for sel in selectors[1:]:
            combined = combined.or_(page.locator(sel))
        try:
            await combined.first.wait_for(state="visible", timeout=timeout)
            return combined.first
        except Exception:
            return None

    async def _check_interrupted(self, db: AsyncSession, task_id: str):
        """检查任务是否被暂停或取消"""
        stmt = select(InsMindAccount.status).where(
            InsMindAccount.id == task_id
        )
        # 对于任务级别的暂停检查，使用全局状态
        from app.models.task_record import TaskRecord
        stmt = select(TaskRecord.status).where(TaskRecord.task_id == task_id)
        result = await db.execute(stmt)
        status = result.scalar_one_or_none()
        if status in ["paused", "cancelled"]:
            raise TaskInterruptedError(f"Task is {status}")

    async def _report_step(self, db: AsyncSession, task_id: str, step: str):
        """上报进度步骤"""
        try:
            await db.execute(
                update(TaskRecord)
                .where(TaskRecord.task_id == task_id)
                .values(current_step=step)
            )
            await db.commit()
        except Exception:
            pass

    async def execute_registration(
        self,
        db: AsyncSession,
        task_id: str,
        proxy_node: Optional[ProxyNode] = None,
        proxy_config: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """执行完整注册流程

        insMind 注册流程（已验证通过）：
        1. 从 temp-mail.io 获取临时邮箱
        2. 导航到 insMind
        3. 点击 "Log in/Sign up"
        4. 点击 "Continue with email"
        5. 输入邮箱
        6. 点击 "Email verification"
        7. 从 temp-mail.io 获取验证码
        8. 填入验证码
        9. 点击 "Log In"
        10. 提取 token/cookie
        """
        result = {
            "success": False,
            "email": None,
            "token": None,
            "cookies": [],
            "error": None,
            "step": "init",
        }

        context = None
        page = None

        try:
            # Step 1: 生成临时邮箱
            result["step"] = "generate_email"
            await self._report_step(db, task_id, result["step"])
            email = await temp_mail_client.generate_email()
            if not email:
                raise Exception("无法生成临时邮箱")
            result["email"] = email

            # Step 2: 创建浏览器上下文
            result["step"] = "create_browser"
            await self._report_step(db, task_id, result["step"])

            playwright_proxy = None
            if proxy_config:
                if proxy_config.host == "127.0.0.1":
                    protocol = proxy_config.protocol or "http"
                    server = (
                        proxy_config.host
                        if "://" in proxy_config.host
                        else f"{protocol}://{proxy_config.host}"
                    )
                    playwright_proxy = {
                        "server": f"{server}:{proxy_config.port}",
                        "username": proxy_config.username,
                        "password": proxy_config.password,
                    }
                else:
                    if proxy_config.group == "external":
                        raise Exception(
                            f"外部代理 {proxy_config.name} 未映射至本地隧道池"
                        )
                    switched = await clash_manager.switch_node(proxy_config.name)
                    playwright_proxy = {
                        "server": f"{settings.clash_proxy_protocol}://127.0.0.1:{settings.clash_proxy_port}"
                    }

            # 创建浏览器
            browser = await self.playwright.chromium.launch(
                headless=settings.browser_headless,
                proxy=playwright_proxy,
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                locale="en-US",
                timezone_id="America/New_York",
            )
            page = await context.new_page()

            # 应用反检测
            if hasattr(self.browser_stealth, "apply_stealth"):
                await self.browser_stealth.apply_stealth(page)

            # Step 3: 导航到 insMind
            result["step"] = "navigate"
            await self._report_step(db, task_id, result["step"])
            await page.goto(settings.insmind_url, wait_until="networkidle")
            await page.wait_for_timeout(2000)

            # Step 4: 点击 "Log in/Sign up" 按钮
            result["step"] = "click_login"
            await self._report_step(db, task_id, result["step"])

            login_btn = await self._find_element(page, "login_button", 10000)
            if not login_btn:
                raise Exception("找不到 Log in/Sign up 按钮")
            await login_btn.click()
            await page.wait_for_timeout(1500)

            # Step 5: 点击 "Continue with email"
            result["step"] = "click_continue_email"
            await self._report_step(db, task_id, result["step"])

            email_btn = await self._find_element(page, "continue_email", 5000)
            if email_btn:
                await email_btn.click()
                await page.wait_for_timeout(1500)

            # 判断当前页面状态：是 email+password 表单还是 code 页面
            # 先找 email+password 登录表单
            email_input = await self._find_element(page, "email_input", 5000)
            if not email_input:
                raise Exception("找不到邮箱输入框")

            # Step 6: 输入邮箱
            result["step"] = "fill_email"
            await self._report_step(db, task_id, result["step"])
            await email_input.fill(email)
            await page.wait_for_timeout(500)

            # Step 7: 点击 "Email verification" 发送验证码
            result["step"] = "send_verification"
            await self._report_step(db, task_id, result["step"])

            email_ver_btn = await self._find_element(page, "email_password_login", 5000)
            if email_ver_btn:
                await email_ver_btn.click()
                await page.wait_for_timeout(2000)

            # 点 "Send code" 按钮（如果有的话）
            send_code_btn = await self._find_element(page, "send_code", 5000)
            if send_code_btn:
                await send_code_btn.click()
                await page.wait_for_timeout(2000)

            # Step 8: 等待并获取验证码
            result["step"] = "wait_code"
            await self._report_step(db, task_id, result["step"])

            code = await temp_mail_client.wait_for_code(
                email,
                timeout=settings.insmind_verification_timeout,
            )
            if not code:
                raise Exception("验证码获取超时")

            # Step 9: 输入验证码
            result["step"] = "input_code"
            await self._report_step(db, task_id, result["step"])

            code_input = await self._find_element(page, "verification_code_input", 5000)
            if code_input:
                await code_input.fill(code)
                await page.wait_for_timeout(500)
            else:
                # 尝试直接输入到可见输入框
                inputs = page.locator('input:not([type="hidden"])')
                count = await inputs.count()
                for i in range(count):
                    ip = inputs.nth(i)
                    ph = await ip.get_attribute("placeholder") or ""
                    if "code" in ph.lower() or "verification" in ph.lower():
                        await ip.fill(code)
                        break

            # Step 10: 点击 "Log In" 提交
            result["step"] = "submit_login"
            await self._report_step(db, task_id, result["step"])

            login_btn = await self._find_element(page, "login_submit", 5000)
            if login_btn:
                await login_btn.click()
                await page.wait_for_timeout(5000)
            else:
                # 回车提交
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(5000)

            # Step 11: 提取 token
            result["step"] = "extract_token"
            await self._report_step(db, task_id, result["step"])

            extractor = TokenExtractor(page, context)
            token_result = await extractor.extract_all()
            result["token"] = token_result.get("token")
            result["cookies"] = token_result.get("cookies", [])

            # 验证是否登录成功（检查页面是否包含登录态元素）
            try:
                avatar = page.locator('[class*="avatar"], [class*="user"], img[alt*="GD"], [class*="profile"]')
                await avatar.first.wait_for(state="visible", timeout=5000)
                result["success"] = True
                logger.info(f"邮箱 {email} 注册成功，token: {result['token'][:30] if result['token'] else 'N/A'}...")
            except Exception:
                # 登录可能失败但页面已变化
                current_url = page.url
                if current_url != settings.insmind_url:
                    result["success"] = True
                    logger.info(f"邮箱 {email} 注册可能成功 (URL: {current_url})")
                else:
                    raise Exception("登录后未检测到登录态，可能验证码错误或风控拦截")

        except TaskInterruptedError:
            result["error"] = "Task interrupted"
            logger.info(f"任务 {task_id} 被中断")
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"注册失败: {e}")
            # 截图
            if page:
                try:
                    screenshot = await page.screenshot(full_page=True)
                    result["screenshot"] = screenshot.hex()[:200]
                except Exception:
                    pass
        finally:
            if context:
                try:
                    await context.close()
                except Exception:
                    pass
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass

        return result

    async def save_account(
        self, db: AsyncSession, result: Dict[str, Any]
    ) -> Optional[InsMindAccount]:
        """保存注册成功的账号到数据库"""
        if not result.get("success"):
            return None

        account = InsMindAccount(
            email=result["email"],
            token=result.get("token") or json.dumps(result.get("cookies", [])),
            status="active",
        )
        db.add(account)
        await db.commit()
        await db.refresh(account)
        logger.info(f"账号已保存: {account.email} (ID: {account.id})")
        return account


# 全局实例
insmind_register_engine = InsMindRegisterEngine()