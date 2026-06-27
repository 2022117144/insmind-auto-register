"""
Dreamina Auto Register - 人类行为模拟模块
"""
import asyncio
import random
from typing import Optional, Tuple
from playwright.async_api import Page, ElementHandle
import logging

logger = logging.getLogger(__name__)


class HumanBehavior:
    """人类行为模拟器"""
    
    def __init__(self, page: Page):
        self.page = page
    
    async def random_delay(self, min_ms: int = 100, max_ms: int = 500):
        """随机延迟"""
        delay = random.randint(min_ms, max_ms)
        await asyncio.sleep(delay / 1000)
    
    async def type_like_human(
        self, 
        selector: str, 
        text: str,
        min_delay: int = 10,
        max_delay: int = 30,
        clear_first: bool = True
    ):
        """
        模拟人类打字
        
        Args:
            selector: 输入框选择器
            text: 要输入的文本
            min_delay: 最小字符间隔（ms）
            max_delay: 最大字符间隔（ms）
            clear_first: 是否先清空输入框
        """
        element = await self.page.wait_for_selector(selector, state="visible")
        if not element:
            raise Exception(f"找不到元素: {selector}")
        
        # 先点击聚焦
        await self.click_like_human(selector)
        await self.random_delay(50, 100)
        
        # 清空现有内容
        if clear_first:
            await self.page.keyboard.press("Control+a")
            await self.random_delay(20, 50)
            await self.page.keyboard.press("Backspace")
            await self.random_delay(30, 80)
        
        for char in text:
            await self.page.keyboard.type(char)
            delay = random.randint(min_delay, max_delay)
            await asyncio.sleep(delay / 1000)
    
    async def click_like_human(
        self, 
        selector: str,
        offset_range: int = 5
    ):
        """
        模拟人类点击：悬停 -> 抖动 -> 点击
        """
        element = await self.page.wait_for_selector(selector, state="visible")
        if not element:
            raise Exception(f"找不到元素: {selector}")
        
        # 1. 先进行悬停
        await self.hover_like_human(selector)
        await self.random_delay(50, 150)
        
        # 2. 执行点击点偏移计算
        box = await element.bounding_box()
        if not box:
            await element.click(force=True)
            return
            
        click_x = box["x"] + box["width"] / 2 + random.randint(-offset_range, offset_range)
        click_y = box["y"] + box["height"] / 2 + random.randint(-offset_range, offset_range)
        
        # 3. 点击
        await self.page.mouse.click(click_x, click_y)
        logger.debug(f"已模拟人类点击: {selector}")

    async def hover_like_human(self, selector: str):
        """模拟人手悬停动作"""
        element = await self.page.wait_for_selector(selector, state="visible")
        box = await element.bounding_box()
        if not box: return
        
        target_x = box["x"] + box["width"] / 2 + random.randint(-3, 3)
        target_y = box["y"] + box["height"] / 2 + random.randint(-3, 3)
        
        await self._move_mouse_naturally(target_x, target_y)
        # 悬停时微小的抖动
        for _ in range(random.randint(1, 3)):
            await self.page.mouse.move(
                target_x + random.uniform(-1, 1), 
                target_y + random.uniform(-1, 1)
            )
            await asyncio.sleep(random.uniform(0.1, 0.3))

    async def _move_mouse_naturally(self, target_x: float, target_y: float):
        """自然地移动鼠标到目标位置 (带有贝塞尔/缓动特征的抖动轨迹)"""
        steps = random.randint(15, 30)
        
        # 假设当前大概位置 (Playwright 无法获取真实 mouse pos，模拟从上一个点或中心开始)
        # 为简化，每次移动视作一个独立轨迹
        viewport = self.page.viewport_size or {"width": 1280, "height": 720}
        start_x = random.uniform(0, viewport["width"])
        start_y = random.uniform(0, viewport["height"])
        
        for i in range(steps):
            progress = (i + 1) / steps
            eased_progress = self._ease_out_quad(progress)
            
            # 基础路径 + 路径上的随机扰动(Jitter)
            current_x = start_x + (target_x - start_x) * eased_progress + random.uniform(-2, 2)
            current_y = start_y + (target_y - start_y) * eased_progress + random.uniform(-2, 2)
            
            await self.page.mouse.move(current_x, current_y)
            # 速度不均匀
            await asyncio.sleep(random.uniform(0.005, 0.02))
    
    @staticmethod
    def _ease_out_quad(t: float) -> float:
        """缓出二次函数"""
        return t * (2 - t)
    
    async def scroll_randomly(self, direction: str = "down", distance: Optional[int] = None):
        """
        随机滚动页面
        
        Args:
            direction: 滚动方向 "up" 或 "down"
            distance: 滚动距离（像素），None 则随机
        """
        if distance is None:
            distance = random.randint(100, 400)
        
        if direction == "up":
            distance = -distance
        
        await self.page.mouse.wheel(0, distance)
        await self.random_delay(300, 800)
    
    async def reading_pause(self, min_seconds: float = 0.3, max_seconds: float = 1.0):
        """模拟阅读停顿"""
        pause_time = random.uniform(min_seconds, max_seconds)
        logger.debug(f"阅读停顿: {pause_time:.1f}s")
        await asyncio.sleep(pause_time)
    
    async def fill_form_field(self, selector: str, value: str):
        """填写表单字段（带人类行为）"""
        await self.random_delay(300, 800)
        await self.type_like_human(selector, value)
        await self.random_delay(200, 500)
    
    async def select_dropdown(self, selector: str, value: str):
        """选择下拉选项"""
        await self.click_like_human(selector)
        await self.random_delay(300, 600)
        
        # 查找并点击选项
        option_selector = f"{selector} option[value='{value}'], [data-value='{value}']"
        try:
            await self.page.click(option_selector)
        except:
            # 备选方案：使用 select_option
            await self.page.select_option(selector, value)
        
        await self.random_delay(200, 400)
    
    async def wait_for_navigation_stable(self, timeout: int = 5000):
        """等待页面导航稳定"""
        try:
            await self.page.wait_for_load_state("networkidle", timeout=timeout)
        except:
            # 超时但页面可能已经可用
            pass
        await self.random_delay(500, 1000)
    
    async def close_popup_if_exists(self, close_selectors: list = None):
        """
        尝试关闭可能出现的弹窗
        """
        if close_selectors is None:
            close_selectors = [
                'button:has-text("Close")',
                'button:has-text("Skip")',
                'button:has-text("Not now")',
                'button:has-text("No thanks")',
                '[aria-label="Close"]',
                '.close-button',
                '.modal-close',
            ]
        
        for selector in close_selectors:
            try:
                element = await self.page.query_selector(selector)
                if element and await element.is_visible():
                    await self.click_like_human(selector)
                    logger.info(f"关闭弹窗: {selector}")
                    await self.random_delay(500, 1000)
                    return True
            except:
                continue
        
        return False
