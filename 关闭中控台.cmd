@echo off
setlocal
title Ecommerce AI Control Center - Stop
cd /d "%~dp0"

where pnpm.cmd >nul 2>nul
if errorlevel 1 (
    echo [ERROR] pnpm.cmd was not found in PATH.
    pause
    exit /b 1
)

call pnpm.cmd dev:down
if errorlevel 1 (
    echo.
    echo [ERROR] Control Center failed to stop. Keep this window for diagnostics.
    pause
    exit /b 1
)

echo.
echo [OK] Control Center processes are stopped.
exit /b 0
