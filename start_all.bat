@echo off
chcp 65001 >nul
cd /d "E:\视频生成\dreamina-auto-register-main"

echo [1/3] Starting insmind2api...
start "insmind2api" cmd /c "node E:\视频生成\dreamina-auto-register-main\insmind2api\dist\index.js"
ping 127.0.0.1 -n 4 >nul

echo [2/3] Starting Backend...
start "Backend" cmd /c "cd /d E:\视频生成\dreamina-auto-register-main\backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8005"
ping 127.0.0.1 -n 6 >nul

echo [3/3] Starting Frontend...
start "Frontend" cmd /c "node E:\视频生成\dreamina-auto-register-main\frontend\node_modules\vite\bin\vite.js --port 5176 --strictPort"

echo.
echo All 3 services launched!
echo Frontend: http://localhost:5176
echo.
pause