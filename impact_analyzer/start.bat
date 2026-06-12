@echo off
title Impact Analyzer Launcher
color 0A

echo.
echo  =====================================================
echo   Impact Analyzer - Starting...
echo  =====================================================
echo.

:: ── Locate Python ─────────────────────────────────────
set PYTHON=
for %%P in (
    "C:\Program Files\Python314\python.exe"
    "C:\Program Files\Python313\python.exe"
    "C:\Program Files\Python312\python.exe"
    "C:\Program Files\Python311\python.exe"
    "C:\Python314\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
) do (
    if exist %%P (
        set PYTHON=%%P
        goto found_python
    )
)
where python >nul 2>&1
if %errorlevel%==0 set PYTHON=python
if defined PYTHON goto found_python
echo  [ERROR] Python not found. Install Python 3.11+ and try again.
pause & exit /b 1
:found_python
echo  [OK] Python: %PYTHON%

:: ── Locate npm ────────────────────────────────────────
set NPM=
for %%N in (
    "C:\Program Files\nodejs\npm.cmd"
    "C:\Program Files\nodejs\npm.bat"
    "%APPDATA%\npm\npm.cmd"
) do (
    if exist %%N (
        set NPM=%%N
        goto found_npm
    )
)
where npm >nul 2>&1
if %errorlevel%==0 set NPM=npm
if defined NPM goto found_npm
echo  [ERROR] npm not found. Install Node.js and try again.
pause & exit /b 1
:found_npm
echo  [OK] npm:    %NPM%

:: ── Paths ─────────────────────────────────────────────
set BACKEND_DIR=%~dp0backend
set FRONTEND_DIR=%~dp0frontend

:: ── Check if backend already running ──────────────────
curl -s --max-time 2 http://localhost:8003/api/bedrock-status >nul 2>&1
if %errorlevel%==0 (
    echo  [WARN] Backend already running on port 8003.
    goto start_frontend
)

:: ── Start backend ─────────────────────────────────────
echo.
echo  Starting backend on http://localhost:8003 ...
start "VaultBot Backend" /D "%BACKEND_DIR%" %PYTHON% -m uvicorn main:app --reload --port 8003

:: ── Wait for backend to be ready (curl health check) ──
echo  Waiting for backend to be ready...
set /a WAIT=0
:wait_loop
timeout /t 3 /nobreak >nul
curl -s --max-time 2 http://localhost:8003/api/bedrock-status >nul 2>&1
if %errorlevel%==0 goto backend_ready
set /a WAIT+=1
if %WAIT% LSS 15 goto wait_loop
echo  [ERROR] Backend did not respond within 45 seconds.
echo  Check the VaultBot Backend window for errors.
pause & exit /b 1
:backend_ready
echo  [OK] Backend is ready.

:: ── Start frontend ────────────────────────────────────
:start_frontend
curl -s --max-time 2 http://localhost:5173 >nul 2>&1
if %errorlevel%==0 (
    echo  [WARN] Frontend already running on port 5173.
    goto open_browser
)

echo.
echo  Starting frontend on http://localhost:5173 ...
start "VaultBot Frontend" /D "%FRONTEND_DIR%" %NPM% run dev

echo  Waiting for frontend to be ready...
timeout /t 8 /nobreak >nul

:: ── Open browser ──────────────────────────────────────
:open_browser
echo.
echo  =====================================================
echo   Impact Analyzer is running!
echo.
echo   Frontend : http://localhost:5173
echo   Backend  : http://localhost:8003
echo   API docs : http://localhost:8003/docs
echo  =====================================================
echo.
echo  Opening browser...
start http://localhost:5173

echo.
echo  Close the Backend and Frontend windows to stop the tool.
echo  Press any key to exit this launcher.
pause >nul
