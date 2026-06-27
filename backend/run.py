
import sys
import asyncio
import os

# Windows specific event loop policy fix for Playwright
if sys.platform == 'win32':
    try:
        from asyncio import WindowsProactorEventLoopPolicy
        if not isinstance(asyncio.get_event_loop_policy(), WindowsProactorEventLoopPolicy):
            asyncio.set_event_loop_policy(WindowsProactorEventLoopPolicy())
    except Exception:
        pass

if __name__ == "__main__":
    import uvicorn
    # Ensure backend directory is in python path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    # Run uvicorn with reload=True
    # The import of app.main inside uvicorn worker will also trigger the policy set in main.py
    # But setting it here ensures the main process has it too.
    uvicorn.run("app.main:app", host="0.0.0.0", port=8005, reload=False, loop="asyncio")
