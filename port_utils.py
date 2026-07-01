"""端口工具 - 纯 Python socket 实现，绝不卡死"""
import socket
import subprocess
import sys
import time


def _check_listen_socket(port):
    """用 socket connect 检测端口是否被监听（毫秒级，绝不卡）"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        s.connect(("127.0.0.1", port))
        s.close()
        return True
    except (ConnectionRefusedError, OSError, socket.timeout):
        return False
    finally:
        s.close()


def kill_port(port):
    """杀掉占用端口的进程 - 先用 socket 检测，再用 wmic（不会卡）"""
    port = int(port)
    if not _check_listen_socket(port):
        print(f"No running process found on port {port}")
        return

    # 用 wmic 查进程（比 netstat 可靠）
    try:
        result = subprocess.run(
            ["wmic", "process", "where", f"commandline like '%:{port}%'",
             "get", "processid,name", "/format:csv"],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.splitlines():
            parts = line.strip().split(",")
            if len(parts) >= 3 and parts[-1].strip().isdigit():
                pid = parts[-1].strip()
                name = parts[-2].strip() if parts[-2] else "process"
                subprocess.run(["taskkill", "/F", "/PID", pid],
                               capture_output=True, timeout=5)
                print(f"Stopping {name} PID {pid} on port {port}")
                return
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass

    print(f"Found listener on port {port} but could not determine PID")


def wait_for_port(port, timeout=45):
    """等待端口开放 - 用 socket 连接检测"""
    port = int(port)
    t = int(timeout)
    start = time.time()
    while time.time() - start < t:
        if _check_listen_socket(port):
            print(f"Listening on port {port}")
            return 0
        time.sleep(1)
    print(f"ERROR: Port {port} did not open within {t}s")
    return 1


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} kill|wait <port> [timeout]")
        sys.exit(1)

    action = sys.argv[1]
    port = sys.argv[2]

    if action == "kill":
        kill_port(port)
    elif action == "wait":
        timeout = sys.argv[3] if len(sys.argv) > 3 else 45
        sys.exit(wait_for_port(port, timeout))
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)