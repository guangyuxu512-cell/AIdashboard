@echo off
setlocal
chcp 65001 >nul
title Yingdao Read-only Diagnostic
cd /d "%~dp0"
echo 正在采集影刀只读诊断信息，请保持影刀已启动并登录目标账号。
echo 不会读取密码、Cookie、Token 或应用变量。
yingdao-diagnostic.exe --output "%~dp0yingdao-diagnostic.json"
if errorlevel 1 (
    echo.
    echo 诊断失败，请截图保留上方错误信息。
    pause
    exit /b 1
)
echo.
echo 诊断完成，请把同目录的 yingdao-diagnostic.json 发回。
pause
