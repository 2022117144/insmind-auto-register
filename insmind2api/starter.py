import subprocess, sys, time, os, signal

node_exe = r'E:\uni\node.exe'
script = r'E:\视频生成\dreamina-auto-register-main\insmind2api\dist\index.js'
cwd = r'E:\视频生成\dreamina-auto-register-main\insmind2api'

proc = subprocess.Popen([node_exe, script], cwd=cwd, 
    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

time.sleep(5)
if proc.poll() is None:
    print(f"PID={proc.pid} RUNNING")
else:
    print(f"EXITED code={proc.returncode}")

try:
    sys.stdin.read()
except:
    proc.kill()
