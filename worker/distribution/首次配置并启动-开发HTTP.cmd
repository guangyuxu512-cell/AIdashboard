@echo off
setlocal
chcp 65001 >nul
echo WARNING: DEV ONLY. Device Token will be sent over plaintext HTTP.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0worker-control.ps1" -Action Configure -StartAfterConfigure -AllowInsecureDevelopment
pause
