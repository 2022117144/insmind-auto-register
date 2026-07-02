"""Launch insMind services in three persistent, independent cmd windows.

Each service runs in its own cmd window — closing the window kills that service.
The launcher script exits after launching all three; the windows are independent.

Usage:
    python start_persistent.py          # interactive (waits for Enter)
    python start_persistent.py --detach # fire-and-forget, exits immediately
"""
import subprocess, time, sys

ROOT = r"E:\视频生成\dreamina-auto-register-main"

services = [
    ("insmind2api", f'cd /d "{ROOT}\insmind2api" && node dist/index.js'),
    ("Backend",    f'cd /d "{ROOT}\backend" && .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8005'),
    ("Frontend",   f'cd /d "{ROOT}\frontend" && node node_modules\vite\bin\vite.js --port 5176 --strictPort'),
]

for title, cmd in services:
    print(f"[{services.index((title, cmd))+1}/3] Starting {title}...")
    subprocess.Popen([
        "cmd", "/c", "start", title,
        "cmd", "/c", cmd
    ], shell=False)
    time.sleep(5)

print("\nAll 3 services launched in separate windows.")
print("Close each window to stop its service.")

if "--detach" not in sys.argv:
    try:
        input("Press Enter to exit this launcher...")
    except (EOFError, KeyboardInterrupt):
        pass