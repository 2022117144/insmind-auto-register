"""Launch insMind services in persistent, independent cmd windows.

Each service runs in its own cmd window — closing the window kills that service.
The launcher script exits after launching all three; the windows are independent.

Usage:
    python start_persistent.py          # interactive (waits for Enter)
    python start_persistent.py --detach # fire-and-forget, exits immediately
"""
import subprocess, time, sys, os

ROOT = r"E:\视频生成\dreamina-auto-register-main"

# ── Dependency check: insmind2api (Node.js) ──────────────────────
INSMIND2API_DIR = os.path.join(ROOT, "insmind2api")
if not os.path.isdir(os.path.join(INSMIND2API_DIR, "node_modules", "koa")):
    print("[setup] insmind2api: installing Node.js dependencies...")
    subprocess.run(["npm", "install"], cwd=INSMIND2API_DIR, check=True)
    print("[setup] insmind2api: done.")

# ── Dependency check: backend (Python) ───────────────────────────
BACKEND_DIR = os.path.join(ROOT, "backend")
VENV_PYTHON = os.path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe")
VENV_PIP = os.path.join(BACKEND_DIR, ".venv", "Scripts", "pip.exe")
REQUIREMENTS = os.path.join(BACKEND_DIR, "requirements.txt")

if not os.path.isfile(VENV_PYTHON):
    print("[setup] backend: creating virtual environment...")
    subprocess.run(["uv", "venv", ".venv"], cwd=BACKEND_DIR, check=True)
    print("[setup] backend: venv created.")

if not os.path.isdir(os.path.join(BACKEND_DIR, ".venv", "Lib", "site-packages", "fastapi")):
    print("[setup] backend: installing Python dependencies...")
    subprocess.run([VENV_PIP, "install", "-r", REQUIREMENTS], check=True)
    print("[setup] backend: done.")

# ── Platform browser: Playwright ─────────────────────────────────
if os.path.isfile(VENV_PYTHON):
    pw_check = subprocess.run(
        [VENV_PYTHON, "-c", "import patchright; print('ok')"],
        capture_output=True, text=True
    )
    if pw_check.returncode != 0 or 'ok' not in pw_check.stdout:
        print("[setup] backend: installing Playwright browsers...")
        subprocess.run([VENV_PYTHON, "-m", "patchright", "install", "chromium"], check=True)
        print("[setup] backend: Playwright browsers installed.")

# ── Services ─────────────────────────────────────────────────────
NODE_EXE = r"E:\uni\node.exe"

services = [
    ("insmind2api", NODE_EXE, ['dist/index.js'], INSMIND2API_DIR),
    ("Backend",    VENV_PYTHON, ['run.py'], BACKEND_DIR),
]

for i, (title, exe, args, cwd) in enumerate(services):
    print(f"[{i+1}/{len(services)}] Starting {title}...")
    subprocess.Popen(
        ["powershell", "-Command",
         f'Start-Process -WindowStyle Normal -FilePath "{exe}" -ArgumentList \'{ " ".join(args) }\' -WorkingDirectory "{cwd}"'],
        shell=False,
    )
    time.sleep(5)

print(f"\nAll {len(services)} services launched in separate windows.")
print("Close each window to stop its service.")

if "--detach" not in sys.argv:
    try:
        input("Press Enter to exit this launcher...")
    except (EOFError, KeyboardInterrupt):
        pass