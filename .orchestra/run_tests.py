"""
insMind 全量测试 — Hermes/Harness 执行脚本
1. 启动 insmind2api（Node.js :5105）
2. 后端 API 健康检查
3. API 端点冒烟
4. 运行现有测试脚本
5. 前端 SPA 验证
6. 汇总报告
"""
import sys, os, json, subprocess, time, yaml, asyncio, httpx
from pathlib import Path

INSPROJECT = "E:/视频生成/dreamina-auto-register-main"
ORCHESTRA = "D:/Orchestra/backend"

# ── 插入 Orchestra 路径以导入 FsStateManager ──
sys.path.insert(0, ORCHESTRA)
os.chdir(ORCHESTRA)

def _call_webhook(event: dict):
    try:
        import requests
        resp = requests.post("http://localhost:8645/webhook", json=event, timeout=5)
        return resp.ok
    except: return None

# ── 工具函数 ──

def check_port(port: int, name: str, timeout_s: int = 3) -> bool:
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout_s)
        r = s.connect_ex(('127.0.0.1', port))
        s.close()
        return r == 0
    except: return False

def http_get(url: str, timeout_s: int = 10) -> dict:
    try:
        import requests
        r = requests.get(url, timeout=timeout_s, headers={"Accept": "application/json"})
        return {"status": r.status_code, "body": r.text[:500], "ok": r.ok}
    except Exception as e:
        return {"status": 0, "body": str(e), "ok": False}

def http_post(url: str, data: dict = None, timeout_s: int = 10) -> dict:
    try:
        import requests
        r = requests.post(url, json=data, timeout=timeout_s)
        return {"status": r.status_code, "body": r.text[:500], "ok": r.ok}
    except Exception as e:
        return {"status": 0, "body": str(e), "ok": False}

def log_step(task_id: str, msg: str):
    print(f"[{task_id}] {msg}")

def update_plan(task_id: str, state: str, note: str = ""):
    p = Path(INSPROJECT) / ".orchestra" / "plan.yaml"
    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    tasks = data.get("tasks", [])
    for t in tasks:
        if t["id"] == task_id:
            t["state"] = state
            if note:
                t["result"] = note[:200]
            break
    with open(p, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=False)
    _call_webhook({"type": "task.completed", "task_id": task_id, "state": state, "note": note[:200]})

# ══════════════════════════════════════════
# 任务执行
# ══════════════════════════════════════════

def run_all_tests():
    results = {}

    # ── T1: 启动 insmind2api ──
    print("\n" + "="*60)
    print("T1: 启动 insmind2api (Node.js :5105)")
    print("="*60)
    
    if check_port(5105, "insmind2api"):
        log_step("T1", "insmind2api 已在运行")
        results["T1"] = {"pass": True, "detail": "已在运行 :5105"}
        update_plan("T1", "✅", "insmind2api 已在运行 :5105")
    else:
        insmind_dir = Path(INSPROJECT) / "insmind2api"
        node_bin = "node"
        try:
            proc = subprocess.Popen(
                [node_bin, str(insmind_dir / "start.js")],
                cwd=str(insmind_dir),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATED_NO_WINDOW') else 0
            )
            # 等 5 秒确认启动
            time.sleep(5)
            for _ in range(6):  # 最多等 30 秒
                if check_port(5105, "insmind2api"):
                    break
                time.sleep(5)
            
            if check_port(5105, "insmind2api"):
                log_step("T1", f"启动成功 PID={proc.pid}")
                results["T1"] = {"pass": True, "detail": f"PID={proc.pid} :5105"}
                update_plan("T1", "✅", f"启动成功 PID={proc.pid}")
            else:
                log_step("T1", "❌ 启动失败")
                results["T1"] = {"pass": False, "detail": "启动失败，端口 :5105 未监听"}
                update_plan("T1", "❌", "启动失败 :5105 未监听")
        except Exception as e:
            log_step("T1", f"❌ 异常: {e}")
            results["T1"] = {"pass": False, "detail": str(e)}
            update_plan("T1", "❌", str(e)[:200])

    # ── T2: 后端健康检查 ──
    print("\n" + "="*60)
    print("T2: 后端 API 健康检查")
    print("="*60)
    
    backend_ok = check_port(8005, "backend")
    if not backend_ok:
        log_step("T2", "❌ Backend :8005 未运行")
        results["T2"] = {"pass": False, "detail": "Backend :8005 未运行"}
        update_plan("T2", "❌", "Backend :8005 未运行")
    else:
        # Health check
        health = http_get("http://localhost:8005/api/health")
        log_step("T2", f"/api/health → {health['status']}")
        
        checks = {"health": health}
        
        # 尝试获取页面（前端 SPA）
        index = http_get("http://localhost:8005/")
        log_step("T2", f"SPA → {index['status']}")
        checks["spa"] = index
        
        all_ok = all(c["ok"] for c in checks.values())
        if all_ok:
            results["T2"] = {"pass": True, "detail": f"health={health['status']} SPA={index['status']}"}
            update_plan("T2", "✅", f"健康检查通过 health={health['status']}")
        else:
            results["T2"] = {"pass": False, "detail": json.dumps({k: v['status'] for k,v in checks.items()})}
            update_plan("T2", "⚠️", "部分端点异常")

    # ── T3: API 端点冒烟测试 ──
    print("\n" + "="*60)
    print("T3: API 端点冒烟测试")
    print("="*60)
    
    api_endpoints = [
        ("/api/insmind/accounts", "insMind 账号"),
        ("/api/accounts", "Dreamina 账号"),
        ("/api/proxies", "代理列表"),
        ("/api/settings", "系统设置"),
        ("/api/dashboard", "仪表盘"),
    ]
    
    api_results = {}
    for path, name in api_endpoints:
        url = f"http://localhost:8005{path}"
        resp = http_get(url)
        ok = resp["ok"]
        api_results[name] = {"ok": ok, "status": resp["status"]}
        log_step("T3", f"  {'✅' if ok else '❌'} {name} → {resp['status']}")
    
    all_api_ok = all(r["ok"] for r in api_results.values())
    if all_api_ok:
        results["T3"] = {"pass": True, "detail": "全部端点通过"}
        update_plan("T3", "✅", f"全部 {len(api_endpoints)} 个端点通过")
    else:
        fails = [k for k, v in api_results.items() if not v["ok"]]
        results["T3"] = {"pass": False, "detail": f"失败: {fails}"}
        update_plan("T3", "⚠️", f"部分失败: {fails}")

    # ── T4: 运行现有测试脚本 ──
    print("\n" + "="*60)
    print("T4: 运行测试脚本")
    print("="*60)
    
    test_scripts = [
        ("test_insmind_token.py", "Token 格式验证"),
        ("test_harness_fixes.py", "Harness 修复验证"),
    ]
    
    test_results = []
    all_tests_pass = True
    for script, desc in test_scripts:
        spath = Path(INSPROJECT) / script
        if not spath.exists():
            log_step("T4", f"  ⏭️ {script} 不存在")
            continue
        
        log_step("T4", f"  运行 {script}...")
        try:
            r = subprocess.run(
                [sys.executable, str(spath)],
                capture_output=True, text=True, timeout=120,
                cwd=INSPROJECT,
            )
            passed = r.returncode == 0
            out = r.stdout.strip()[-200:] if r.stdout else ""
            err = r.stderr.strip()[-200:] if r.stderr else ""
            status = "✅" if passed else "❌"
            log_step("T4", f"  {status} {script} exit={r.returncode}")
            test_results.append({"script": script, "passed": passed, "output": out, "error": err})
            if not passed: all_tests_pass = False
        except subprocess.TimeoutExpired:
            log_step("T4", f"  ❌ {script} 超时")
            test_results.append({"script": script, "passed": False, "output": "", "error": "Timeout"})
            all_tests_pass = False
        except Exception as e:
            log_step("T4", f"  ❌ {script} 异常: {e}")
            test_results.append({"script": script, "passed": False, "output": "", "error": str(e)})
            all_tests_pass = False
    
    if all_tests_pass:
        results["T4"] = {"pass": True, "detail": f"全部 {len(test_results)} 个测试通过"}
        update_plan("T4", "✅", f"{len(test_results)} 测试通过")
    else:
        fails = [r["script"] for r in test_results if not r["passed"]]
        results["T4"] = {"pass": False, "detail": f"失败: {fails}"}
        update_plan("T4", "⚠️", f"部分失败: {fails}")

    # ── T5: 前端 SPA 验证 ──
    print("\n" + "="*60)
    print("T5: 前端 SPA 验证")
    print("="*60)
    
    dist_dir = Path(INSPROJECT) / "frontend" / "dist"
    if not dist_dir.exists():
        log_step("T5", "❌ frontend/dist 不存在")
        results["T5"] = {"pass": False, "detail": "dist 不存在"}
        update_plan("T5", "❌", "frontend/dist 不存在")
    else:
        # 检查关键文件
        index_html = dist_dir / "index.html"
        assets_dir = dist_dir / "assets"
        has_index = index_html.exists()
        has_assets = assets_dir.exists() and any(assets_dir.iterdir())
        
        log_step("T5", f"  index.html: {'✅' if has_index else '❌'}")
        log_step("T5", f"  assets/: {'✅' if has_assets else '❌'}")
        
        # 通过后端访问 SPA
        spa = http_get("http://localhost:8005/")
        spa_ok = spa["ok"] or "index.html" in spa["body"]
        
        if has_index and has_assets and spa_ok:
            results["T5"] = {"pass": True, "detail": "前端构建完整，SPA 可访问"}
            update_plan("T5", "✅", "前端构建完整，SPA 可访问")
        else:
            detail = f"index={'✅' if has_index else '❌'} assets={'✅' if has_assets else '❌'} spa={'✅' if spa_ok else '❌'}"
            results["T5"] = {"pass": has_index and has_assets, "detail": detail}
            update_plan("T5", "⚠️", detail)

    # ── T6: 汇总报告 ──
    print("\n" + "="*60)
    print("T6: 测试报告汇总")
    print("="*60)
    
    passed_count = sum(1 for r in results.values() if r["pass"])
    total_count = len(results)
    
    report = []
    report.append("# insMind 全量测试报告")
    report.append(f"**时间**: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"**结果**: {passed_count}/{total_count} 通过")
    report.append("")
    report.append("| 任务 | 描述 | 结果 |")
    report.append("|------|------|------|")
    
    for tid in ["T1", "T2", "T3", "T4", "T5"]:
        r = results.get(tid, {"pass": False, "detail": "未执行"})
        emoji = "✅" if r["pass"] else "❌"
        names = {"T1": "insmind2api 启动", "T2": "后端健康检查", "T3": "API 冒烟", "T4": "测试脚本", "T5": "前端 SPA"}
        report.append(f"| {tid} | {names.get(tid,tid)} | {emoji} {r['detail'][:80]} |")
    
    report.append("")
    report.append("---")
    report.append("*Harness 全量测试完成*")
    
    report_text = "\n".join(report)
    print(report_text)
    
    results["T6"] = {"pass": passed_count == total_count, "detail": f"{passed_count}/{total_count} 通过"}
    update_plan("T6", "✅" if passed_count == total_count else "⚠️", f"{passed_count}/{total_count} 通过")
    
    return results, report_text

if __name__ == "__main__":
    results, report = run_all_tests()
    print("\n\n✅ 测试执行完毕")
