Ecommerce AI Worker for Windows
================================

首次接入
1. 在中控台创建独立 Device，并由 Backend CLI 为该 Device 签发一次性 Token。
2. 双击“首次配置并启动.cmd”。
3. 输入 Backend HTTPS URL、Device ID、Device Token。
4. 如果此电脑安装影刀，可同时填写包含 shadowbot.shell-cli.exe 和 ShadowBot.exe 的安装根目录。

日常使用
- 启动Worker.cmd：检查配置和现有实例后在后台启动。
- 停止Worker.cmd：只停止状态文件精确记录的本 Worker PID。
- 查看状态.cmd：显示进程、Backend、Device ID、Server URL 和设备连接状态。

安全说明
- 公网 Backend URL 必须使用 HTTPS。
- Token 由 Windows DPAPI 按当前用户加密，配置保存在
  %LOCALAPPDATA%\EcommerceAIWorker\config.json。
- 日志和任务 Runtime 也位于该用户私有目录，不写入发行包目录。
- 本包不包含 SSH Key、数据库配置、Device ID、Device Token、店铺凭证或 Cookie。
- 普通执行电脑不需要 SSH、公网 IP、端口映射、Backend、PostgreSQL 或项目源码。

当前能力
- system.echo
- system.sleep
- yingdao.discover（只读；需要本机影刀已安装并登录）

不包含 Windows Service、自动更新、真实影刀 App 执行或浏览器登录。
