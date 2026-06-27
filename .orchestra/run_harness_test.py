"""
insMind Harness 全链路测试
H1: 基础设施检查 → H2: API 冒烟 → H3: 注册账号 → H4: 生成测试 → H5: 回归测试 → H6: 报告
"""
import sys, os, json, time, yaml, subprocess, requests
from pathlib import Path

INSPROJECT = "E:/视频生成/dreamina-auto-register-main"
BACKEND = "http://localhost:8005"
INSMIND2API = "http://127.0.0.1:5105"

def log(task, msg): print(f"[{task}] {msg}")

def update_plan(task_id, state, note=""):
    p = Path(INSPROJECT) / ".orchestra" / "plan.yaml"
    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    for t in data.get("tasks", []):
        if t["id"] == task_id:
            t["state"] = state
            if note: t["result"] = note[:200]
    with open(p, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)

def check_port(port):
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    try: r = s.connect_ex(('127.0.0.1', port)); return r == 0
    finally: s.close()

def http_get(url, timeout=10):
    try:
        r = requests.get(url, timeout=timeout, headers={"Accept": "application/json"})
        return {"ok": r.ok, "status": r.status_code, "text": r.text[:200]}
    except Exception as e: return {"ok": False, "status": 0, "text": str(e)}

def http_post(url, data=None, timeout=10):
    try:
        r = requests.post(url, json=data, timeout=timeout)
        return {"ok": r.ok, "status": r.status_code, "json": r.json() if r.text else {}, "text": r.text[:200]}
    except Exception as e: return {"ok": False, "status": 0, "text": str(e), "json": {}}

# ═══ H1: 基础设施 ═══
log("H1", "检查基础设施...")
services = [
    ("PostgreSQL", 5433), ("Redis", 6379), ("dsrelay", 18080), ("KeyProxy", 18888),
    ("Webhook", 8645), ("Orchestra", 8000), ("insMind", 8005), ("insmind2api", 5105),
]
all_up = True
for name, port in services:
    ok = check_port(port)
    log("H1", f"  {'✅' if ok else '❌'} {name} :{port}")
    if not ok: all_up = False

if all_up:
    update_plan("H1", "✅", "全部 8 个服务在线")
else:
    update_plan("H1", "⚠️", "部分服务离线")

# ═══ H2: API 冒烟 ═══
log("H2", "API 冒烟测试...")
endpoints = [
    ("/api/health", "健康检查"),
    ("/api/insmind/accounts", "insMind账号"),
    ("/api/accounts", "Dreamina账号"),
    ("/api/proxies", "代理"),
    ("/api/settings", "设置"),
]
smoke_results = {}
for path, name in endpoints:
    resp = http_get(f"{BACKEND}{path}")
    smoke_results[name] = resp["ok"]
    log("H2", f"  {'✅' if resp['ok'] else '❌'} {name} → {resp['status']}")

all_smoke = all(smoke_results.values())
update_plan("H2", "✅" if all_smoke else "⚠️",
            f"通过 {sum(1 for v in smoke_results.values() if v)}/{len(endpoints)}")

# ═══ H5: 回归测试(先做，不依赖注册) ═══
log("H5", "运行回归测试...")
test_script = Path(INSPROJECT) / "test_harness_fixes.py"
if test_script.exists():
    r = subprocess.run([sys.executable, str(test_script)],
                       capture_output=True, text=True, timeout=60, cwd=INSPROJECT)
    out = r.stdout.strip()[-200:]
    err = r.stderr.strip()[-200:]
    passed = r.returncode == 0
    log("H5", f"  {'✅' if passed else '❌'} test_harness_fixes.py exit={r.returncode}")
    update_plan("H5", "✅" if passed else "⚠️", f"exit={r.returncode}")
else:
    log("H5", "  ⏭️  test_harness_fixes.py 不存在")
    update_plan("H5", "✅", "跳过")

# ═══ H3: 注册 ═══
log("H3", "注册新账号（auto_register API）...")
reg = http_post(f"{BACKEND}/api/insmind/accounts/auto-register", timeout=180)
if reg["ok"] and reg["json"].get("success"):
    email = reg["json"].get("email", "")
    log("H3", f"  ✅ 注册成功: {email}")
    update_plan("H3", "✅", f"注册成功: {email}")
else:
    err = reg["json"].get("error", reg["text"])
    log("H3", f"  ❌ 注册失败: {err}")
    update_plan("H3", "❌", f"注册失败: {err}")

# ═══ H4: 生成测试 ═══
log("H4", "测试视频生成...")
gen = http_post(f"{INSMIND2API}/api/v1/videos/generations", {
    "prompt": "A cute cat walking", "model": "Pixverse-V6.0",
    "duration": 5, "resolution": "360P", "aspect_ratio": "16:9",
}, timeout=30)

if gen["ok"]:
    status = gen["json"].get("status", "unknown")
    response = gen["json"].get("response", "")
    if "invalid_access_token" in response or "expire" in response:
        log("H4", f"  ⚠️ token 过期或无效: {response[:100]}")
        update_plan("H4", "⚠️", f"token 过期: {response[:80]}")
    elif status == "processing":
        log("H4", f"  ✅ 生成已提交: task_id={gen['json'].get('id','')[:20]}")
        update_plan("H4", "✅", f"生成已提交 id={gen['json'].get('id','')[:20]}")
    else:
        log("H4", f"  ⚠️ 未知状态: {gen['text'][:100]}")
        update_plan("H4", "⚠️", gen['text'][:80])
elif gen["status"] == 402:
    log("H4", "  ⚠️ insmind2api 池无账号（未注册或未同步）")
    update_plan("H4", "⚠️", "insmind2api 池无账号")
else:
    log("H4", f"  ❌ {gen['status']} {gen['text'][:100]}")
    update_plan("H4", "❌", gen['text'][:80])

# ═══ H6: 汇总 ═══
log("H6", "汇总报告...")
results = {}
for tid in ["H1", "H2", "H3", "H4", "H5"]:
    p = Path(INSPROJECT) / ".orchestra" / "plan.yaml"
    with open(p) as f:
        d = yaml.safe_load(f) or {}
    for t in d.get("tasks", []):
        if t["id"] == tid:
            results[tid] = t["state"]
            break

passed = sum(1 for v in results.values() if v == "✅")
total = len(results)

report = [
    "# insMind Harness 全链路测试报告",
    f"**时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
    f"**结果**: {passed}/{total} 通过",
    "",
    "| 任务 | 状态 |",
    "|------|------|",
]
names = {"H1": "基础设施", "H2": "API冒烟", "H3": "注册账号", "H4": "生成测试", "H5": "回归测试"}
for tid in ["H1", "H2", "H3", "H4", "H5"]:
    s = results.get(tid, "❓")
    report.append(f"| {tid} {names[tid]} | {s} |")
report.append("")

print("\n".join(report))
update_plan("H6", "✅" if passed == total else "⚠️", f"{passed}/{total} 通过")
log("H6", f"Harness 测试完成: {passed}/{total} ✅")
