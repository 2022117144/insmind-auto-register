@echo off
cd /d E:\视频生成\dreamina-auto-register-main\insmind2api
node dist\index.js
if %ERRORLEVEL% NEQ 0 (
    echo NODE_EXIT_CODE=%ERRORLEVEL% > &2
)
pause