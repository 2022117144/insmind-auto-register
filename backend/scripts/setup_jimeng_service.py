
import httpx
import zipfile
import io
import os
import shutil

PROXY = "http://127.0.0.1:7897"
URL = "https://github.com/iptag/jimeng-api/archive/refs/heads/main.zip"
TARGET_BASE = "e:/PRJ-WORK/jimeng-auto-register/backend/jimeng_service"

def download_and_setup():
    print(f"Downloading {URL} via {PROXY}...")
    try:
        with httpx.Client(proxy=PROXY, verify=False, follow_redirects=True, timeout=60.0) as client:
            r = client.get(URL)
            if r.status_code != 200:
                print(f"Failed status: {r.status_code}")
                return

            print("Extracting...")
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                # Get the root folder name in zip (e.g. jimeng-api-main)
                root_folder = z.namelist()[0].split('/')[0]
                temp_extract = os.path.join(TARGET_BASE, "temp_extract")
                z.extractall(temp_extract)
                
                source_path = os.path.join(temp_extract, root_folder)
                
                # Move all files from source_path to TARGET_BASE
                for item in os.listdir(source_path):
                    s = os.path.join(source_path, item)
                    d = os.path.join(TARGET_BASE, item)
                    if os.path.exists(d):
                        if os.path.isdir(d): shutil.rmtree(d)
                        else: os.remove(d)
                    shutil.move(s, d)
                
                # Cleanup temp
                shutil.rmtree(temp_extract)
                print(f"Setup complete in {TARGET_BASE}")
            
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    if not os.path.exists(TARGET_BASE):
        os.makedirs(TARGET_BASE)
    download_and_setup()
