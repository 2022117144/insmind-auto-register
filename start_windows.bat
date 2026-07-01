@echo off
chcp 65001 >nul 2>nul
cd /d "E:\视频生成\dreamina-auto-register-main"

echo [1/3] Starting insmind2api...
start "insmind2api" node insmind2api\dist\index.js
ping -n 4 127.0.0.1 >nul

echo [2/3] Starting Backend...
start "Backend" cmd /c "cd /d E:\视频生成\dreamina-auto-register-main\backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8005"
ping -n 6 127.0.0.1 >nul

echo [3/3] Starting Frontend...
start "Frontend" cmd /c "node E:\视频生成\dreamina-auto-register-main\frontend\node_modules\vite\bin\vite.js --port 5176 --strictPort"

echo All services launched in separate windows.