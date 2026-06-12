@echo off
title VaultBot Launcher

echo ==========================================
echo   VaultBot Help Assistant
echo ==========================================
echo.

:: ── Step 1: Start Backend ─────────────────────────────────────────────────────
echo [1/3] Starting backend...
start "VaultBot Backend" cmd /k "cd /d %~dp0backend && python -m uvicorn main:app --host 127.0.0.1 --port 8000"

:: ── Step 2: Poll backend with progress bar ────────────────────────────────────
echo [2/3] Backend loading:
powershell -NoProfile -Command ^
  "$cr=[char]13; $sp='|','/','-','+'; $i=0; $e=0;" ^
  "while($true){" ^
  "  try{" ^
  "    Invoke-WebRequest 'http://127.0.0.1:8000/health' -UseBasicParsing -TimeoutSec 2 | Out-Null;" ^
  "    Write-Host ($cr + '      [##########] 100%% - Ready!          ') -ForegroundColor Green;" ^
  "    break" ^
  "  } catch {" ^
  "    $p = [Math]::Min($e * 5, 95);" ^
  "    $f = [int]($p / 10);" ^
  "    $bar = '##########'.Substring(0,$f) + '----------'.Substring(0,10-$f);" ^
  "    Write-Host -NoNewline ($cr + '      [' + $bar + '] ' + $p + '%% ' + $sp[$i%%4] + '  ');" ^
  "    $i++; $e++; Start-Sleep 1" ^
  "  }" ^
  "}"

:: ── Step 3: Start Frontend ────────────────────────────────────────────────────
echo.
echo [3/3] Starting frontend...
start "VaultBot Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

:: ── Poll frontend with spinner ────────────────────────────────────────────────
echo       Frontend loading:
powershell -NoProfile -Command ^
  "$cr=[char]13; $sp='|','/','-','+'; $i=0;" ^
  "while($true){" ^
  "  try{" ^
  "    Invoke-WebRequest 'http://localhost:5173' -UseBasicParsing -TimeoutSec 2 | Out-Null;" ^
  "    Write-Host ($cr + '      [##########] Ready!               ') -ForegroundColor Green;" ^
  "    break" ^
  "  } catch {" ^
  "    Write-Host -NoNewline ($cr + '      [' + $sp[$i%%4] + '] Waiting for frontend...  ');" ^
  "    $i++; Start-Sleep 1" ^
  "  }" ^
  "}"

:: ── Open browser ──────────────────────────────────────────────────────────────
echo.
echo ==========================================
echo   VaultBot is ready!
echo   Opening http://localhost:5173 ...
echo ==========================================
echo.
start "" "http://localhost:5173"

echo   To stop: close the Backend and Frontend windows.
echo.
pause
