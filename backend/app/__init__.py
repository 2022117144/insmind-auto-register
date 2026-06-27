import sys
import asyncio

# Windows 下使用 Playwright 必须使用 ProactorEventLoop
if sys.platform == 'win32':
    try:
        from asyncio import WindowsProactorEventLoopPolicy
        if not isinstance(asyncio.get_event_loop_policy(), WindowsProactorEventLoopPolicy):
            asyncio.set_event_loop_policy(WindowsProactorEventLoopPolicy())
    except Exception:
        pass

"""
Dreamina Auto Register - App Module
"""
