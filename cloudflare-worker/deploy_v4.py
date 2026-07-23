#!/usr/bin/env python3
"""Deploy dreamina-email-worker via CF API (Service Worker format)"""
import json, os, httpx

cfg_path = os.path.join(os.path.dirname(__file__), "config.json")
with open(cfg_path) as f:
    cfg = json.load(f)

ACCOUNT = cfg["account_id"]
TOKEN = cfg["api_token"]
KV_NS = cfg["kv_namespace_id"]
WORKER_NAME = "dreamina-email-worker"

# Read the pre-compiled JS
js_path = os.path.join(os.path.dirname(__file__), "dist", "worker.js")
with open(js_path, "r", encoding="utf-8") as f:
    js = f.read()

print(f"JS size: {len(js)} bytes")

# For Service Worker format, metadata without main_module
metadata = json.dumps({
    "body_part": "script",
    "compatibility_date": "2024-01-01",
    "bindings": [
        {"name": "EMAIL_CODES", "namespace_id": KV_NS, "type": "kv_namespace"}
    ],
})

boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
parts = []
parts.append(f"--{boundary}\r\n".encode())
parts.append(b'Content-Disposition: form-data; name="metadata"\r\n')
parts.append(b"Content-Type: application/json\r\n\r\n")
parts.append(metadata.encode("utf-8"))
parts.append(b"\r\n")
parts.append(f"--{boundary}\r\n".encode())
parts.append(b'Content-Disposition: form-data; name="script"; filename="worker.js"\r\n')
parts.append(b"Content-Type: application/javascript\r\n\r\n")
parts.append(js.encode("utf-8"))
parts.append(b"\r\n")
parts.append(f"--{boundary}--\r\n".encode())
body = b"".join(parts)

url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/workers/scripts/{WORKER_NAME}"
headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": f"multipart/form-data; boundary={boundary}",
}

print(f"Uploading ({len(body)} bytes)...")
with httpx.Client(timeout=60) as client:
    resp = client.put(url, headers=headers, content=body)

print(f"Status: {resp.status_code}")
data = resp.json()
if data.get("success"):
    print(f"✅ Worker '{WORKER_NAME}' deployed!")
else:
    print(f"❌ Failed: {json.dumps(data.get('errors', data), indent=2, ensure_ascii=False)}")