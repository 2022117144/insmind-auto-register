
import sys
import asyncio
import os

# 强制指定证书路径（修复项目路径含中文导致 libcurl 加载失败）
os.environ["SSL_CERT_FILE"] = r"C:\Users\Administrator\cacert.pem"
os.environ["REQUESTS_CA_BUNDLE"] = r"C:\Users\Administrator\cacert.pem"

# Windows specific event loop policy fix for Playwright
if sys.platform == 'win32':
    try:
        from asyncio import WindowsProactorEventLoopPolicy
        if not isinstance(asyncio.get_event_loop_policy(), WindowsProactorEventLoopPolicy):
            asyncio.set_event_loop_policy(WindowsProactorEventLoopPolicy())
    except Exception:
        pass

if __name__ == "__main__":
    import socket
    import uvicorn
    from uvicorn import Config, Server
    
    # Ensure backend directory is in python path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    # Pre-bind socket with SO_REUSEADDR to bypass Windows zombie TCP sockets
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", 8005))
    sock.listen(128)
    
    config = Config(app="app.main:app", host="0.0.0.0", port=8005, loop="asyncio")
    server = Server(config=config)
    server.run(sockets=[sock])
