"""Stop insMind services launched by start_persistent.py.

Usage:
    python stop_persistent.py          # interactive (waits for Enter)
    python stop_persistent.py --detach # fire-and-forget, exits immediately
"""
import subprocess, sys, os

ROOT = r"E:\视频生成\dreamina-auto-register-main"

# ── Find and kill the processes ──────────────────────────────────
# insmind2api: node.exe running dist/index.js
# Backend: python.exe running uvicorn app.main:app

print("Stopping insMind services...")

# Kill insmind2api (node.exe listening on :5105)
result = subprocess.run(
    ['powershell', '-Command',
     'Get-NetTCPConnection -LocalPort 5105 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess'],
    capture_output=True, text=True, timeout=10
)
if result.stdout.strip():
    pids = [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
    for pid in pids:
        subprocess.run(['taskkill', '/PID', pid, '/F'], capture_output=True)
        print(f"  ✅ 已终止 insmind2api (PID {pid})")
else:
    print("  ⏭️  insmind2api 未运行")

# Kill backend (python.exe listening on :8005)
result = subprocess.run(
    ['powershell', '-Command',
     'Get-NetTCPConnection -LocalPort 8005 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess'],
    capture_output=True, text=True, timeout=10
)
if result.stdout.strip():
    pids = [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
    for pid in pids:
        subprocess.run(['taskkill', '/PID', pid, '/F'], capture_output=True)
        print(f"  ✅ 已终止 Backend (PID {pid})")
else:
    print("  ⏭️  Backend 未运行")

print("\nDone.")

if "--detach" not in sys.argv:
    try:
        input("Press Enter to exit...")
    except (EOFError, KeyboardInterrupt):
        pass