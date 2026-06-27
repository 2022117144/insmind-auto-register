"""Sync accounts from accounts.json to backend DB"""
import json, httpx

with open("E:/视频生成/dreamina-auto-register-main/insmind2api/configs/accounts.json") as f:
    pool = json.load(f)

print(f"账户池有 {len(pool)} 个")

for a in pool:
    email = a["email"]
    token = a["token"]
    uid = a.get("userId", "0")

    r = httpx.post("http://localhost:8005/api/insmind/accounts", json={
        "email": email, "token": token, "user_id": uid, "credits": 0, "status": "active",
    }, timeout=10)
    if r.status_code == 201:
        print(f"  ✅ {email}")
    elif r.status_code == 409:
        print(f"  ⏭️ {email}  exists")
    else:
        print(f"  ❌ {email}: {r.status_code}")

r = httpx.get("http://localhost:8005/api/insmind/accounts", timeout=10)
data = r.json()
print(f"\nDB now has {len(data)} accounts")
for a in data:
    tok = a.get("token", "")
    if tok:
        import base64
        padded = tok + "=" * (4 - len(tok) % 4)
        d = json.loads(base64.urlsafe_b64decode(padded))
        inner = d.get("access_token", "")
        parts = inner.split(".")
        if len(parts) >= 2:
            p2 = parts[1] + "=" * (4 - len(parts[1]) % 4)
            payload = json.loads(base64.urlsafe_b64decode(p2))
            exp = payload.get("exp", 0)
            from datetime import datetime
            rem = (datetime.fromtimestamp(exp) - datetime.now()).total_seconds() / 3600
            print(f"  {a['email'][:22]:<22} expires_in={rem:.1f}h")