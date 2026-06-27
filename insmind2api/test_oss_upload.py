import httpx, json, sqlite3, base64, io, hashlib, hmac
from PIL import Image
from datetime import timezone, datetime

db = sqlite3.connect('e:/视频生成/dreamina-auto-register-main/backend/data/dreamina.db')
cur = db.cursor()
cur.execute('SELECT email, token, user_id, org_id FROM insmind_accounts ORDER BY id DESC LIMIT 1')
row = cur.fetchone()
db.close()
padded = row[1] + '=' * (4 - len(row[1]) % 4)
inner = json.loads(base64.urlsafe_b64decode(padded)).get('access_token', '')

# STS
sts = httpx.post('https://www.insmind.com/api/tb-dam/asset/upload/tokens',
    json={'format':'jpg','content_id':'','dir':'','device_id':'test'},
    headers={
        'Content-Type':'application/json',
        'Authorization':f'Bearer {inner}',
        'x-product-type':'INDIVIDUAL_FREE',
        'x-channel-id':'781','x-business-id':'124','x-device-id':'test',
        'x-language':'en','x-legal-region':'US','x-locale':'en-US','x-market':'GLOBAL',
        'origin':'https://www.insmind.com','referer':'https://www.insmind.com/creation',
        'Cookie': f'token.prod={row[1]}; token.org_id.prod={row[3]}',
    },
    proxy='http://127.0.0.1:7897', timeout=30).json()

# Image
img = Image.new('RGB', (100, 100), (50, 120, 200))
buf = io.BytesIO()
img.save(buf, format='JPEG', quality=85)
img_bytes = buf.getvalue()

key = sts['object_name']
date_str = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')
bucket = sts['bucket_name']
content_type = 'image/jpeg'

# Build OSS auth - exactly like calculateOssAuth in insmind2api
resource = f'/{bucket}/{key}'
oss_header_line = f'x-oss-security-token:{sts["security_token"]}'
string_to_sign = f'PUT\n\n{content_type}\n{date_str}\n{oss_header_line}\n{resource}'
signature = base64.b64encode(hmac.new(sts['access_key_secret'].encode(), string_to_sign.encode(), hashlib.sha1).digest()).decode()
auth = f'OSS {sts["access_key_id"]}:{signature}'

# Try CDN host
url = f'{sts["host"]}/{key}'
print(f'PUT: {url}')
r = httpx.put(url, content=img_bytes,
    headers={
        'Content-Type': content_type,
        'Date': date_str,
        'Authorization': auth,
        'x-oss-security-token': sts['security_token'],
    },
    timeout=30, verify=False)
print(f'Status: {r.status_code}')
if r.status_code == 200:
    print(f'✅ SUCCESS: {url}')
else:
    print(r.text[:300])