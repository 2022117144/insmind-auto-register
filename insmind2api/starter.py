import subprocess, sys, time, os, signal

node_exe = r'E:\uni\node.exe'
script = r'E:\视频生成\dreamina-auto-register-main\insmind2api\dist\index.js'
cwd = r'E:\视频生成\dreamina-auto-register-main\insmind2api'
log_dir = os.path.join(cwd, 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'server.log')

# 追加模式打开日志文件
log_fd = open(log_file, 'a')

proc = subprocess.Popen([node_exe, script], cwd=cwd, 
    stdin=subprocess.DEVNULL, stdout=log_fd, stderr=log_fd,
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

log_fd.write(f"\n=== [started] PID={proc.pid} ===\n")
log_fd.flush()

time.sleep(5)
if proc.poll() is None:
    print(f"PID={proc.pid} RUNNING (log: {log_file})")
else:
    print(f"EXITED code={proc.returncode} (check log: {log_file})")

try:
    sys.stdin.read()
except:
    proc.kill()
    log_fd.close()