@echo off
setlocal

set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%"

if not exist "logs" mkdir "logs"
set "LOG_FILE=%ROOT_DIR%logs\run_app.log"

echo [%date% %time%] launcher start>>"%LOG_FILE%"

set "PYTHON_EXE=%ROOT_DIR%.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

set "PYTHONPATH=%ROOT_DIR%src"
set "AMON_UI_PORT=8000"
set "AMON_UI_URL=http://127.0.0.1:%AMON_UI_PORT%/#/chat"

start "Amon UI Server" cmd /c ""%PYTHON_EXE%" -m amon.cli ui --port %AMON_UI_PORT% >> "%LOG_FILE%" 2>&1"

set "READY="
for /L %%I in (1,1,40) do (
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "try { $r = Invoke-WebRequest -UseBasicParsing '%AMON_UI_URL%' -TimeoutSec 2; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { exit 0 } else { exit 1 } } catch { exit 1 }"
  if not errorlevel 1 (
    set "READY=1"
    goto open_browser
  )
  timeout /t 1 /nobreak >nul
)

:open_browser
start "" "%AMON_UI_URL%"

if defined READY (
  echo [%date% %time%] ui ready %AMON_UI_URL%>>"%LOG_FILE%"
) else (
  echo [%date% %time%] ui probe timeout, browser opened anyway %AMON_UI_URL%>>"%LOG_FILE%"
)

exit /b 0
