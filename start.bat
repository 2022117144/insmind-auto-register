@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

cd /d "%~dp0" || (
    echo [ERROR] Failed to enter project root.
    pause
    exit /b 1
)

title Dreamina Auto Register

set "ROOT=%CD%"
set "BACKEND_DIR=%ROOT%\backend"
set "FRONTEND_DIR=%ROOT%\frontend"
set "JIMENG_DIR=%BACKEND_DIR%\jimeng_service"
set "LOG_DIR=%BACKEND_DIR%\logs\startup"
set "CHECK_ONLY=0"

if /i "%~1"=="--check" set "CHECK_ONLY=1"

echo.
echo ========================================
echo   Dreamina Auto Register - v2.2.0
echo ========================================
echo.
echo [INFO] Project root: %ROOT%
if "%CHECK_ONLY%"=="1" echo [INFO] Check mode enabled. Services will not be started.
echo.

if not exist "%BACKEND_DIR%\data" mkdir "%BACKEND_DIR%\data" >nul 2>nul
if not exist "%BACKEND_DIR%\data\screenshots" mkdir "%BACKEND_DIR%\data\screenshots" >nul 2>nul
if not exist "%BACKEND_DIR%\data\browser_states" mkdir "%BACKEND_DIR%\data\browser_states" >nul 2>nul
if not exist "%BACKEND_DIR%\logs" mkdir "%BACKEND_DIR%\logs" >nul 2>nul
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>nul

echo [CHECK] Verifying runtime commands...
call :detect_python || goto :fail
call :detect_node || goto :fail

echo [CHECK] Python launcher: %PYTHON_CMD%
call %PYTHON_CMD% --version || goto :fail
echo [CHECK] Node executable: node
node --version || goto :fail
echo [CHECK] NPM executable: %NPM_CMD%
call "%NPM_CMD%" --version || goto :fail
echo.

echo [CLEAN] Stopping old services...
call :kill_port 8005 Backend
call :kill_port 5175 Frontend
call :kill_port 5105 JimengAPI
timeout /t 1 /nobreak >nul
echo [CLEAN] Done.
echo.

if not exist "%BACKEND_DIR%\.env" (
    echo [CONFIG] backend\.env not found. Creating from template...
    copy "%BACKEND_DIR%\.env.example" "%BACKEND_DIR%\.env" >nul
    if errorlevel 1 (
        echo [ERROR] Failed to create backend\.env
        goto :fail
    )
    echo.
    echo ========================================================
    echo   backend\.env was created from .env.example
    echo   Edit it first, then run start.bat again.
    echo ========================================================
    echo.
    pause
    exit /b 0
)

echo [1/4] Preparing Python environment...
if not exist "%BACKEND_DIR%\.venv\Scripts\python.exe" (
    echo       Creating virtual environment...
    call %PYTHON_CMD% -m venv "%BACKEND_DIR%\.venv" || goto :fail
)

set "VENV_PYTHON=%BACKEND_DIR%\.venv\Scripts\python.exe"
set "PATCHRIGHT_EXE=%BACKEND_DIR%\.venv\Scripts\patchright.exe"

if not exist "%VENV_PYTHON%" (
    echo [ERROR] Virtual environment python.exe not found.
    goto :fail
)

echo       Installing Python dependencies...
REM 暂时禁用代理，pip 走直连连清华镜像源
set "NO_PROXY=*"
set "no_proxy=*"
set "HTTP_PROXY="
set "HTTPS_PROXY="
set "http_proxy="
set "https_proxy="
"%VENV_PYTHON%" -m pip install --disable-pip-version-check --trusted-host pypi.tuna.tsinghua.edu.cn -r "%BACKEND_DIR%\requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple || goto :fail

if not exist "%PATCHRIGHT_EXE%" (
    echo [ERROR] patchright.exe not found after dependency installation.
    goto :fail
)

if not exist "%BACKEND_DIR%\.venv\.patchright-ready" (
    echo       Installing Patchright browser...
    call "%PATCHRIGHT_EXE%" install chromium || goto :fail
    > "%BACKEND_DIR%\.venv\.patchright-ready" echo ready
)

echo       Python environment ........ OK
echo.

echo [2/4] Preparing Jimeng API service...
pushd "%JIMENG_DIR%" || goto :fail
if exist "package-lock.json" (
    call "%NPM_CMD%" ci --include=dev --no-audit --no-fund --loglevel error || (
        popd
        goto :fail
    )
) else (
    call "%NPM_CMD%" install --include=dev --no-audit --no-fund --loglevel error || (
        popd
        goto :fail
    )
)
popd
echo       Jimeng API ................ OK
echo.

echo [3/4] Preparing Frontend...
pushd "%FRONTEND_DIR%" || goto :fail
if exist "package-lock.json" (
    call "%NPM_CMD%" ci --include=dev --no-audit --no-fund --loglevel error || (
        popd
        goto :fail
    )
) else (
    call "%NPM_CMD%" install --include=dev --no-audit --no-fund --loglevel error || (
        popd
        goto :fail
    )
)
popd
echo       Frontend .................. OK
echo.

if "%CHECK_ONLY%"=="1" (
    echo [CHECK] Validation completed. No services were started.
    echo.
    echo Press any key to exit.
    pause >nul
    exit /b 0
)

set "JIMENG_LOG=%LOG_DIR%\jimeng_service.log"
set "BACKEND_LOG=%LOG_DIR%\backend.log"
set "FRONTEND_LOG=%LOG_DIR%\frontend.log"

type nul > "%JIMENG_LOG%"
type nul > "%BACKEND_LOG%"
type nul > "%FRONTEND_LOG%"

set "RUNNER_SUFFIX=%RANDOM%%RANDOM%%RANDOM%"
set "JIMENG_RUNNER=%TEMP%\dreamina_start_jimeng_%RUNNER_SUFFIX%.bat"
set "BACKEND_RUNNER=%TEMP%\dreamina_start_backend_%RUNNER_SUFFIX%.bat"
set "FRONTEND_RUNNER=%TEMP%\dreamina_start_frontend_%RUNNER_SUFFIX%.bat"

echo [4/4] Starting services...

(
    echo @echo off
    echo chcp 65001 ^>nul 2^>nul
    echo set "PYTHONUTF8=1"
    echo set "PYTHONIOENCODING=utf-8"
    echo cd /d "%JIMENG_DIR%"
    echo call "%NPM_CMD%" run dev ^>^> "%JIMENG_LOG%" 2^>^&1
) > "%JIMENG_RUNNER%"

(
    echo @echo off
    echo chcp 65001 ^>nul 2^>nul
    echo set "PYTHONUTF8=1"
    echo set "PYTHONIOENCODING=utf-8"
    echo cd /d "%BACKEND_DIR%"
    echo "%VENV_PYTHON%" -m uvicorn app.main:app --host 0.0.0.0 --port 8005 --loop asyncio ^>^> "%BACKEND_LOG%" 2^>^&1
) > "%BACKEND_RUNNER%"

(
    echo @echo off
    echo chcp 65001 ^>nul 2^>nul
    echo set "PYTHONUTF8=1"
    echo set "PYTHONIOENCODING=utf-8"
    echo cd /d "%FRONTEND_DIR%"
    echo call "%NPM_CMD%" run dev ^>^> "%FRONTEND_LOG%" 2^>^&1
) > "%FRONTEND_RUNNER%"

start "Dreamina Jimeng API" /b cmd /c ""%JIMENG_RUNNER%""
call :wait_for_port 5105 45 JimengAPI "%JIMENG_LOG%" || goto :startup_fail

start "Dreamina Backend" /b cmd /c ""%BACKEND_RUNNER%""
call :wait_for_port 8005 45 Backend "%BACKEND_LOG%" || goto :startup_fail

start "Dreamina Frontend" /b cmd /c ""%FRONTEND_RUNNER%""
call :wait_for_port 5175 45 Frontend "%FRONTEND_LOG%" || goto :startup_fail

echo.
echo ========================================
echo   All services started successfully.
echo.
echo   Dashboard:  http://localhost:5175
echo   Backend:    http://localhost:8005
echo   API Docs:   http://localhost:8005/docs
echo   Jimeng API: http://localhost:5105
echo.
echo   Logs:
echo     %JIMENG_LOG%
echo     %BACKEND_LOG%
echo     %FRONTEND_LOG%
echo ========================================
echo.

echo Press any key to open the dashboard...
pause >nul
start "" http://localhost:5175

echo.
echo Press any key to stop all services and exit.
pause >nul
goto :cleanup

:startup_fail
echo.
echo [ERROR] One or more services failed to start.
echo [ERROR] Check the log files below:
echo         %JIMENG_LOG%
echo         %BACKEND_LOG%
echo         %FRONTEND_LOG%
echo.
pause
goto :cleanup

:cleanup
echo.
echo [STOP] Stopping services...
call :kill_port 8005 Backend
call :kill_port 5175 Frontend
call :kill_port 5105 JimengAPI
del "%JIMENG_RUNNER%" >nul 2>nul
del "%BACKEND_RUNNER%" >nul 2>nul
del "%FRONTEND_RUNNER%" >nul 2>nul
echo [STOP] Done.
echo.
echo Press any key to exit.
pause >nul
exit /b 0

:fail
echo.
echo [ERROR] start.bat failed.
echo Press any key to exit.
pause >nul
exit /b 1

:detect_python
REM 优先使用 Python 3.12
set "PYTHON_CMD="
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    exit /b 0
)
if exist "C:\Program Files\Python312\python.exe" (
    set "PYTHON_CMD=C:\Program Files\Python312\python.exe"
    exit /b 0
)

where python >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    exit /b 0
)

where py >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
    exit /b 0
)

echo [ERROR] Python 3.10+ was not found in PATH.
exit /b 1

:detect_node
where node >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Node.js 18+ was not found in PATH.
    exit /b 1
)

set "NPM_CMD="
for /f "delims=" %%p in ('where npm.cmd 2^>nul') do (
    if not defined NPM_CMD set "NPM_CMD=%%p"
)
if not defined NPM_CMD (
    echo [ERROR] npm.cmd was not found in PATH.
    exit /b 1
)
exit /b 0

:kill_port
set "TARGET_PORT=%~1"
set "TARGET_NAME=%~2"
%PYTHON_CMD% "%~dp0port_utils.py" kill %TARGET_PORT%
exit /b 0

:wait_for_port
set "TARGET_PORT=%~1"
set "TARGET_TIMEOUT=%~2"
set "TARGET_NAME=%~3"
set "TARGET_LOG=%~4"
%PYTHON_CMD% "%~dp0port_utils.py" wait %TARGET_PORT% %TARGET_TIMEOUT% && (
    echo       !TARGET_NAME! listening on port !TARGET_PORT!
    exit /b 0
)
echo [ERROR] !TARGET_NAME! did not open port !TARGET_PORT! in time.
echo         Log: !TARGET_LOG!
exit /b 1
