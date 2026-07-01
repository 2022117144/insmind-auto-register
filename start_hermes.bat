@echo off
chcp 65001 >nul 2>nul
set ROOT=E:\视频生成\dreamina-auto-register-main
cd /d "%ROOT%"
if not "%1"=="child" (
    start "insmind2api" /min cmd /c "%ROOT%\start_hermes.bat" child insmind2api
    ping -n 4 127.0.0.1 >nul
    start "Backend" /min cmd /c "%ROOT%\start_hermes.bat" child backend
    ping -n 6 127.0.0.1 >nul
    start "Frontend" /min cmd /c "%ROOT%\start_hermes.bat" child frontend
    echo All services launched.
    exit /b 0
)
if "%2"=="insmind2api" node "%ROOT%\insmind2api\dist\index.js"
if "%2"=="backend" cd /d "%ROOT%\backend" && .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8005
if "%2"=="frontend" node "%ROOT%\frontend\node_modules\vite\bin\vite.js" --port 5176 --strictPort