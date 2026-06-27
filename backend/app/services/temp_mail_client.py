"""insMind Auto Register - Temp-Mail.io 客户端

提供临时邮箱生成和验证码获取功能。
支持两种模式：
1. API 模式：直接调用 temp-mail.io REST API
2. 浏览器模式（回退）：通过 Patchright 浏览器访问 temp-mail.io 网页

验证码流程已验证通过（2026-06-17）：
- 邮箱: 9w6qrk8hfe@bltiwd.com
- 发件人: no-reply@info.insmind.com
- 主题: 【insMind】Verify your email
- 验证码: 501363（6位纯数字）
"""

import asyncio
import logging
import re
from typing import Optional
from urllib.parse import urljoin

import httpx

logger = logging.getLogger(__name__)

# Temp-Mail.io API 基础地址
TEMP_MAIL_API_BASE = "https://api.internal.temp-mail.io"  # 免费无鉴权（已验证）
TEMP_MAIL_WEB_URL = "https://temp-mail.io"

# insMind 验证码邮件特征
INSMIND_SENDER = "no-reply@info.insmind.com"
INSMIND_SUBJECT_PATTERN = r"【insMind】Verify your email"
VERIFICATION_CODE_PATTERN = r"(\d{6})"


class TempMailClient:
    """Temp-Mail.io 客户端"""

    def __init__(self, use_api: bool = True):
        self.use_api = use_api
        self._current_email: Optional[str] = None
        self._http_client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url=TEMP_MAIL_API_BASE, timeout=10.0
            )
        return self._http_client

    async def generate_email(self) -> Optional[str]:
        """生成一个新的临时邮箱地址"""
        if self.use_api:
            try:
                client = await self._get_client()
                resp = await client.get("/api/v3/email/new")
                if resp.status_code == 200:
                    data = resp.json()
                    # 常见响应格式: {"email": "xxx@domain.com"}
                    email = data.get("email")
                    if email:
                        self._current_email = email
                        logger.info(f"Temp-mail 已生成: {email}")
                        return email
                logger.warning(
                    f"Temp-mail API 返回异常: {resp.status_code} {resp.text[:200]}"
                )
            except Exception as e:
                logger.warning(f"Temp-mail API 调用失败: {e}，尝试浏览器模式")

        # 浏览器模式回退（通过 Patchright）
        return await self._generate_email_via_browser()

    async def _generate_email_via_browser(self) -> Optional[str]:
        """通过浏览器方式获取临时邮箱（使用 patchright）"""
        try:
            from patchright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(TEMP_MAIL_WEB_URL, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)

                # 页面自动生成邮箱，从输入框提取
                email_input = page.locator("#email")
                email = await email_input.input_value()
                if email:
                    self._current_email = email
                    logger.info(f"Temp-mail (浏览器) 已生成: {email}")
                await browser.close()
                return email
        except Exception as e:
            logger.error(f"Temp-mail 浏览器模式失败: {e}")
            return None

    async def wait_for_code(
        self, email: str, timeout: int = 180, poll_interval: int = 3
    ) -> Optional[str]:
        """轮询收件箱，等待 insMind 验证码

        Args:
            email: 临时邮箱地址
            timeout: 超时时间（秒）
            poll_interval: 轮询间隔（秒）

        Returns:
            验证码（6位数字字符串），超时返回 None
        """
        if self.use_api:
            try:
                client = await self._get_client()
                start_time = asyncio.get_event_loop().time()
                while (asyncio.get_event_loop().time() - start_time) < timeout:
                    try:
                        # 使用完整邮箱地址查询（已验证 api.internal.temp-mail.io 免费无鉴权）
                        resp = await client.get(
                            f"/api/v3/email/{email}/messages"
                        )
                        if resp.status_code == 200:
                            messages = resp.json()
                            if isinstance(messages, list):
                                for msg in messages:
                                    code = self._extract_code(msg)
                                    if code:
                                        logger.info(f"验证码已获取: {code}")
                                        return code
                        elif resp.status_code == 404:
                            # 404 = 没有邮件
                            pass
                    except Exception as e:
                        logger.debug(f"轮询邮件失败: {e}")

                    await asyncio.sleep(poll_interval)

                logger.warning(f"等待验证码超时 ({timeout}s)")
                return None

            except Exception as e:
                logger.warning(f"Temp-mail API 轮询失败: {e}，尝试浏览器模式")

        # 浏览器模式回退
        return await self._wait_for_code_via_browser(email, timeout, poll_interval)

    async def _wait_for_code_via_browser(
        self, email: str, timeout: int, poll_interval: int
    ) -> Optional[str]:
        """通过浏览器轮询收件箱"""
        try:
            from patchright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(f"{TEMP_MAIL_WEB_URL}/zh", wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)

                start_time = asyncio.get_event_loop().time()
                while (asyncio.get_event_loop().time() - start_time) < timeout:
                    # 刷新页面获取最新邮件
                    await page.reload(wait_until="domcontentloaded")
                    await page.wait_for_timeout(2000)

                    # 检查收件箱中是否有 insMind 的邮件
                    page_text = await page.inner_text("body")
                    if "insMind" in page_text and "Verify" in page_text:
                        # 提取验证码
                        match = re.search(VERIFICATION_CODE_PATTERN, page_text)
                        if match:
                            code = match.group(1)
                            logger.info(f"验证码已获取 (浏览器): {code}")
                            await browser.close()
                            return code

                    await asyncio.sleep(poll_interval)

                logger.warning(f"浏览器轮询超时 ({timeout}s)")
                await browser.close()
                return None

        except Exception as e:
            logger.error(f"Temp-mail 浏览器轮询失败: {e}")
            return None

    def _extract_code(self, msg: dict) -> Optional[str]:
        """从邮件数据中提取验证码"""
        # 检查邮件内容
        body = msg.get("body_text", "") or msg.get("body_html", "") or ""
        sender = msg.get("from", "") or msg.get("from_address", "")
        subject = msg.get("subject", "")

        # 过滤非 insMind 邮件
        if "insmind" not in sender.lower() and "insmind" not in subject.lower():
            return None
        if "verify" not in subject.lower() and "验证" not in subject:
            return None

        # 从正文中提取6位数字验证码
        match = re.search(VERIFICATION_CODE_PATTERN, body)
        return match.group(1) if match else None

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None


# 全局实例
temp_mail_client = TempMailClient()