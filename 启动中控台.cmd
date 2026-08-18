@echo off
setlocal
title Ecommerce AI Control Center - Start
cd /d "%~dp0"

where pnpm.cmd >nul 2>nul
if errorlevel 1 (
    echo [ERROR] pnpm.cmd was not found in PATH.
    pause
    exit /b 1
)

call pnpm.cmd dev:up
if errorlevel 1 (
    echo.
    echo [ERROR] Control Center failed to start. Keep this window for diagnostics.
    pause
    exit /b 1
)

echo.
echo [OK] Control Center is running.
exit /b 0
