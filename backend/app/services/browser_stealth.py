"""
Dreamina Auto Register - 浏览器反检测模块
使用 Patchright (Playwright 的反检测分支) + 增强隐身脚本
"""

from typing import Dict, Any, Optional
from patchright.async_api import Browser, BrowserContext, Page, Playwright
import random
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# 地域时区语言一致性矩阵
REGION_TIMEZONE_MAP = {
    "US": {
        "timezone": "America/New_York",
        "locale": "en-US",
        "languages": ["en-US", "en"],
    },
    "UK": {
        "timezone": "Europe/London",
        "locale": "en-GB",
        "languages": ["en-GB", "en"],
    },
    "JP": {
        "timezone": "Asia/Tokyo",
        "locale": "ja-JP",
        "languages": ["ja-JP", "ja", "en-US", "en"],
    },
    "KR": {
        "timezone": "Asia/Seoul",
        "locale": "ko-KR",
        "languages": ["ko-KR", "ko", "en-US", "en"],
    },
    "SG": {
        "timezone": "Asia/Singapore",
        "locale": "en-SG",
        "languages": ["en-SG", "en-US", "en"],
    },
    "HK": {
        "timezone": "Asia/Hong_Kong",
        "locale": "zh-HK",
        "languages": ["zh-HK", "zh", "en-US", "en"],
    },
    "TW": {
        "timezone": "Asia/Taipei",
        "locale": "zh-CN",
        "languages": ["zh-CN", "zh", "en-US", "en"],
    },
    "DE": {
        "timezone": "Europe/Berlin",
        "locale": "de-DE",
        "languages": ["de-DE", "de", "en-US", "en"],
    },
    "FR": {
        "timezone": "Europe/Paris",
        "locale": "fr-FR",
        "languages": ["fr-FR", "fr", "en-US", "en"],
    },
}

# 固定设备画像池 (基于真实 Virtual Browser 提取，确保 UA/硬件/渲染器逻辑闭环)
DEVICE_ARCHETYPES = [
    {
        "name": "Windows-HighEnd-AMD",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        "viewport": {"width": 2048, "height": 1152},
        "hardware_concurrency": 12,
        "device_memory": 64,
        "device_scale_factor": 1.25,
        "renderer": "ANGLE (AMD, AMD Radeon(TM) R5 240 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "vendor": "Google Inc. (AMD)",
    },
    {
        "name": "Macintosh-Standard-NVIDIA",
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "viewport": {"width": 1920, "height": 1080},
        "hardware_concurrency": 4,
        "device_memory": 16,
        "device_scale_factor": 2,
        "renderer": "ANGLE (NVIDIA, NVIDIA GeForce GT 710 Direct3D11 vs_5_0 ps_5_0, D3D11-27.21.14.6109)",
        "vendor": "Google Inc. (NVIDIA)",
    },
    {
        "name": "Windows-Mainstream-Intel",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "viewport": {"width": 1536, "height": 864},
        "hardware_concurrency": 8,
        "device_memory": 32,
        "device_scale_factor": 1.5,
        "renderer": "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "vendor": "Google Inc. (Intel)",
    },
    {
        "name": "Windows-Laptop-Intel-Xe",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
        "viewport": {"width": 1366, "height": 768},
        "hardware_concurrency": 8,
        "device_memory": 16,
        "device_scale_factor": 1,
        "renderer": "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "vendor": "Google Inc. (Intel)",
    },
]


class BrowserStealth:
    """浏览器反检测配置器"""

    def __init__(self, playwright: Playwright):
        self.playwright = playwright

    def get_region_config(self, region_tag: Optional[str]) -> Dict[str, Any]:
        """根据地域标签获取配置"""
        if region_tag and region_tag.upper() in REGION_TIMEZONE_MAP:
            return REGION_TIMEZONE_MAP[region_tag.upper()]
        # 默认使用美国配置
        return REGION_TIMEZONE_MAP["US"]

    def get_random_fingerprint(
        self, region_tag: Optional[str] = None
    ) -> Dict[str, Any]:
        """从画像池中生成指纹画像"""
        region_config = self.get_region_config(region_tag)
        # 固定画像选取
        archetype = random.choice(DEVICE_ARCHETYPES)

        return {
            "archetype_name": archetype["name"],
            "user_agent": archetype["user_agent"],
            "viewport": archetype["viewport"],
            "timezone_id": region_config["timezone"],
            "locale": region_config["locale"],
            "geolocation": None,
            "permissions": [],
            "color_scheme": random.choice(["light", "dark"]),
            "hardware_concurrency": archetype["hardware_concurrency"],
            "device_memory": archetype["device_memory"],
            "device_scale_factor": archetype["device_scale_factor"],
            "extra_http_headers": {
                "Accept-Language": ",".join(region_config["languages"]) + ";q=0.9",
            },
            "renderer": archetype["renderer"],
            "vendor": archetype["vendor"],
        }

    async def launch_browser(self, headless: Optional[bool] = None) -> Browser:
        """启动浏览器（每次独立启动进程，获取真实 TLS 指纹且防止交叉污染）"""
        target_headless = (
            headless if headless is not None else settings.browser_headless
        )

        # Patchright + 反检测启动参数
        args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-features=AutomationControlled",
            "--disable-infobars",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-timer-throttling",
            # 禁止 WebRTC 泄露真实 IP (即便开启了代理)
            "--webrtc-ip-handling-policy=disable_non_proxied_udp",
            "--force-webrtc-ip-handling-policy",
        ]

        # 优先使用系统安装的 Chrome（TLS/JA3 指纹与手动浏览一致，避免 CDN 拦截）
        # channel="chrome" 会自动寻找系统安装的 Chrome/Chromium
        channel = "chrome"
        try:
            logger.info(
                f"启动独立浏览器进程 [Patchright + System Chrome] (Headless: {target_headless})"
            )
            browser = await self.playwright.chromium.launch(
                headless=target_headless,
                channel=channel,
                args=args,
            )
        except Exception as e:
            # 系统未安装 Chrome 时 fallback 到内置 Chromium
            logger.warning(f"系统 Chrome 启动失败: {e}，回退到内置 Chromium")
            browser = await self.playwright.chromium.launch(
                headless=target_headless,
                args=args,
            )

        return browser

    async def create_context(
        self,
        region_tag: Optional[str] = None,
        state_path: Optional[str] = None,
        fingerprint: Optional[Dict[str, Any]] = None,
        proxy: Optional[Dict[str, str]] = None,
        headless: Optional[bool] = None,
    ) -> BrowserContext:
        """
        创建浏览器上下文（带反检测配置）

        Args:
            region_tag: 地域标签，用于匹配时区/语言
            state_path: 浏览器状态文件路径（用于恢复登录态）
            fingerprint: 保存的指纹配置（登录时复用）
            headless: 是否使用无头模式
        """
        browser = await self.launch_browser(headless=headless)

        # 使用保存的指纹或生成新指纹
        if fingerprint:
            fp = fingerprint
        else:
            fp = self.get_random_fingerprint(region_tag)

        # 代理配置：优先使用外部传入的代理，默认使用 Clash 本地代理
        proxy_config = proxy
        if not proxy_config:
            proxy_config = {
                "server": f"{settings.clash_proxy_protocol}://127.0.0.1:{settings.clash_proxy_port}"
            }

        # 上下文配置
        context_options = {
            "user_agent": fp.get("user_agent"),
            "viewport": fp.get("viewport"),
            "timezone_id": fp.get("timezone_id"),
            "locale": fp.get("locale"),
            "color_scheme": fp.get("color_scheme"),
            "extra_http_headers": fp.get("extra_http_headers"),
            "proxy": proxy_config,
            "ignore_https_errors": True,
            # 随机硬件属性
            "device_scale_factor": random.choice([1, 1.25, 1.5, 2]),
            # 屏蔽 WebRTC 真实 IP 泄露 (重要)
            "permissions": ["geolocation"],
        }

        if state_path:
            context_options["storage_state"] = state_path

        context = await browser.new_context(**context_options)

        # 注入硬件指纹伪装脚本
        injection_script = f"""
            Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => {fp.get("hardware_concurrency", 8)} }});
            Object.defineProperty(navigator, 'deviceMemory', {{ get: () => {fp.get("device_memory", 8)} }});
        """
        await context.add_init_script(injection_script)

        # 注入增强反检测脚本
        await self._inject_stealth_scripts(context, fp)

        return context

    async def _inject_stealth_scripts(
        self, context: BrowserContext, fp: Dict[str, Any]
    ):
        """
        注入深度指纹加固脚本 (WebGL, Canvas, Audio)
        """
        renderer = fp.get(
            "renderer",
            "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        )
        vendor = fp.get("vendor", "Google Inc. (Intel)")

        # 为 Canvas 和 Audio 生成一个基于账号邮箱或随机性的种子噪声，以保证同一指纹下噪声稳定
        # 这里简单使用随机值但在 context 生命周期内通过 init_script 固定

        script = f"""
        (() => {{
            // 1. WebGL Vendor/Renderer 伪装 (动态匹配画像)
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {{
                // UNMASKED_VENDOR_WEBGL = 0x9245, UNMASKED_RENDERER_WEBGL = 0x9246
                if (parameter === 37445) return '{vendor}';
                if (parameter === 37446) return '{renderer}';
                return getParameter.apply(this, arguments);
            }};

            // 2. Canvas 噪声注入 (干扰 Canvas 指纹)
            const toDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function() {{
                const context = this.getContext('2d');
                if (context) {{
                    const imageData = context.getImageData(0, 0, this.width, this.height);
                    // 注入极其微小的确定性随机噪声 (在当前页面生命周期内稳定)
                    for (let i = 0; i < 10; i++) {{
                        const idx = Math.floor((i * 12345) % imageData.data.length);
                        imageData.data[idx] = imageData.data[idx] ^ 1;
                    }}
                    context.putImageData(imageData, 0, 0);
                }}
                return toDataURL.apply(this, arguments);
            }};

            // 3. Audio 指纹扰动
            const getChannelData = AudioBuffer.prototype.getChannelData;
            AudioBuffer.prototype.getChannelData = function() {{
                const result = getChannelData.apply(this, arguments);
                if (result.length > 0) {{
                    // 对采样点进行极微小扰动
                    result[result.length - 1] += 1e-7;
                }}
                return result;
            }};

            // 4. Navigator 属性加固
            Object.defineProperty(navigator, 'vendor', {{ get: () => 'Google Inc.' }});
            Object.defineProperty(navigator, 'platform', {{ get: () => 'Win32' }});
        }})();
        """
        await context.add_init_script(script)
        logger.debug(f"深度指纹加固脚本已注入 [{fp.get('archetype_name')}]")

    async def create_page(self, context: BrowserContext) -> Page:
        """创建页面并应用额外配置与流量拦截"""
        page = await context.new_page()

        # 极度省流与反监控拦截策略
        block_domains = [
            "googletagmanager.com",
            "google-analytics.com",
            "mon-sg.capcutapi.com",
            "mon.capcutapi.com",
            "p16-dreamina-sign-sg.ibyteimg.com",
            "p19-dreamina-sign-sg.ibyteimg.com",
            "sf16-web-tos-buz.capcutstatic.com",  # 通常是无关痛痒的资源包
        ]

        async def intercept_traffic(route, request):
            url = request.url
            # 1. 拦截打点和无用的高清大图域名
            if any(domain in url for domain in block_domains):
                await route.abort()
                return

            # 2. 拦截全局的所有音视频 (开启 font 以模拟真实用户特征)
            if request.resource_type in ["media"]:
                await route.abort()
                return

            await route.continue_()

        await page.route("**/*", intercept_traffic)

        # 设置默认超时
        page.set_default_timeout(30000)
        page.set_default_navigation_timeout(60000)

        return page

    async def save_state(self, context: BrowserContext, path: str):
        """保存浏览器状态"""
        await context.storage_state(path=path)
        logger.info(f"浏览器状态已保存: {path}")

    async def close(self):
        """由于浏览器进程现在按需创建与关闭，此全局方法设为空操作"""
        pass

    @staticmethod
    async def dismiss_error_modal(page: Page, max_retries: int = 2) -> bool:
        """
        检测并关闭 Dreamina 的 'Something went wrong' 错误弹窗。

        Args:
            page: 当前页面
            max_retries: 弹窗出现后最大重试次数（点击 Refresh）

        Returns:
            True 如果弹窗被处理，False 如果没有检测到弹窗
        """
        for attempt in range(max_retries):
            try:
                # 检测错误弹窗 (class 包含 dreamina-fatal-error-modal)
                modal = page.locator(
                    '[class*="dreamina-fatal-error-modal"], [class*="fatal-error-modal"]'
                )
                if await modal.count() > 0 and await modal.first.is_visible():
                    logger.warning(
                        f"检测到 Dreamina 错误弹窗 (尝试 {attempt + 1}/{max_retries})，点击 Refresh..."
                    )

                    # 尝试点击 Refresh 按钮
                    refresh_btn = modal.locator(
                        'button:has-text("Refresh"), button:has-text("refresh")'
                    )
                    if await refresh_btn.count() > 0:
                        await refresh_btn.first.click()
                        # 等待页面重新加载
                        await page.wait_for_timeout(3000)
                        try:
                            await page.wait_for_load_state("networkidle", timeout=10000)
                        except Exception:
                            pass
                        logger.info("已点击 Refresh，等待页面恢复...")
                        continue
                    else:
                        # 没有找到按钮，尝试直接刷新页面
                        logger.warning("未找到 Refresh 按钮，直接刷新页面")
                        await page.reload(wait_until="load", timeout=30000)
                        await page.wait_for_timeout(3000)
                        continue
                else:
                    # 没有检测到弹窗
                    return False
            except Exception as e:
                logger.debug(f"弹窗检测异常: {e}")
                return False

        # 最后一轮再检测一次
        try:
            modal = page.locator(
                '[class*="dreamina-fatal-error-modal"], [class*="fatal-error-modal"]'
            )
            if await modal.count() > 0 and await modal.first.is_visible():
                logger.error("多次 Refresh 后弹窗仍然存在")
                return True
        except Exception:
            pass

        return True
