@echo off
setlocal EnableDelayedExpansion
title Impact Analyzer

echo ============================================================
echo  Impact Analyzer - Starting...
echo ============================================================
echo.

:: ── Locate Python ────────────────────────────────────────────
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+ and add it to PATH.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo [OK] Found %PY_VER%

:: ── Move to script directory ─────────────────────────────────
cd /d "%~dp0"

:: ── Install / verify dependencies ────────────────────────────
echo.
echo [1/3] Checking dependencies...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo [OK] Dependencies ready.

:: ── Start backend (FastAPI server) in a new window ───────────
echo.
echo [2/3] Starting backend server on http://localhost:8000 ...
start "Impact Analyzer - Backend" cmd /k "cd /d "%~dp0" && python main.py"

:: ── Wait for the server to become ready ──────────────────────
echo.
echo [3/3] Waiting for server to be ready...
set MAX_WAIT=30
set COUNT=0

:WAIT_LOOP
timeout /t 1 /nobreak >nul
set /a COUNT+=1

python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api', timeout=2)" >nul 2>&1
if not errorlevel 1 goto SERVER_READY

if !COUNT! geq %MAX_WAIT% (
    echo [ERROR] Server did not start within %MAX_WAIT% seconds.
    echo         Check the backend window for errors.
    pause
    exit /b 1
)

<nul set /p "=."
goto WAIT_LOOP

:SERVER_READY
echo.
echo [OK] Server is ready!

:: ── Open the frontend in the default browser ─────────────────
echo.
echo Opening http://localhost:8000 in your browser...
start "" "http://localhost:8000"

echo.
echo ============================================================
echo  Impact Analyzer is running at http://localhost:8000
echo  API docs available at   http://localhost:8000/docs
echo  Close the backend window to stop the server.
echo ============================================================
echo.
endlocal
