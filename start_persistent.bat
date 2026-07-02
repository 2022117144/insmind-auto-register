@echo off
chcp 65001 >nul
set ROOT=E:\视频生成\dreamina-auto-register-main

echo [1/3] Starting insmind2api (:5105)...
start "insmind2api" cmd /c "cd /d "%ROOT%\insmind2api" && node dist/index.js"

timeout /t 4 /nobreak >nul

echo [2/3] Starting Backend (:8005)...
start "Backend" cmd /c "cd /d "%ROOT%\backend" && .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8005"

timeout /t 6 /nobreak >nul

echo [3/3] Starting Frontend (:5176)...
start "Frontend" cmd /c "cd /d "%ROOT%\frontend" && node node_modules\vite\bin\vite.js --port 5176 --strictPort"

echo.
echo All 3 services launched in separate windows.
echo Close each window to stop its service, or press any key to exit this launcher.
echo.
pause
