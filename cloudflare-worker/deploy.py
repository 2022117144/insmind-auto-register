#!/usr/bin/env python3
"""Deploy dreamina-email-worker via CF API (proper multipart with httpx)"""
import json, os, httpx

cfg_path = os.path.join(os.path.dirname(__file__), "config.json")
with open(cfg_path) as f:
    cfg = json.load(f)

ACCOUNT = cfg["account_id"]
TOKEN = cfg["api_token"]
KV_NS = cfg["kv_namespace_id"]
WORKER_NAME = "dreamina-email-worker"

js_path = os.path.join(os.path.dirname(__file__), "dist", "worker.mjs")
with open(js_path, "r", encoding="utf-8") as f:
    js = f.read()

metadata = {
    "main_module": "worker.js",
    "compatibility_date": "2024-01-01",
    "bindings": [
        {"name": "EMAIL_CODES", "namespace_id": KV_NS, "type": "kv_namespace"}
    ],
}

url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/workers/scripts/{WORKER_NAME}"

# Use httpx multipart encoding
with httpx.Client(timeout=60) as client:
    resp = client.put(
        url,
        headers={"Authorization": f"Bearer {TOKEN}"},
        files={
            "metadata": ("metadata.json", json.dumps(metadata), "application/json"),
            "worker.js": ("worker.js", js, "application/javascript+module"),
        },
    )

print(f"Status: {resp.status_code}")
data = resp.json()
if data.get("success"):
    print(f"✅ Worker '{WORKER_NAME}' deployed in ES Module format!")
else:
    print(f"❌ Failed: {json.dumps(data.get('errors', data), indent=2, ensure_ascii=False)}")