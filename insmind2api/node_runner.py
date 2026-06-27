"""
Start insmind2api as a background process.
stdin=DEVNULL avoids "stdin is not a tty" crash.
"""
import subprocess
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_JS = os.path.join(BASE_DIR, "dist", "index.js")
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

log_file = os.path.join(LOG_DIR, "server.log")

with open(log_file, "a") as lf:
    proc = subprocess.Popen(
        ["node", "--require", os.path.join(BASE_DIR, "proxy-bootstrap.js"), DIST_JS],
        cwd=BASE_DIR,
        stdin=subprocess.DEVNULL,
        stdout=lf,
        stderr=lf,
        env={**os.environ, "NODE_OPTIONS": "--dns-result-order=ipv4first", "FORCE_COLOR": "0"},
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS if sys.platform == "win32" else 0,
    )

print(f"insmind2api started PID={proc.pid}, logging to {log_file}")
sys.exit(0)