Ecommerce AI Worker 0.4.8 for Windows
======================================

普通首次接入
1. 在中控台创建 Device，并在设备详情的“Worker 凭证”区域签发 Token。
2. 解压本 ZIP，双击 ecommerce-worker.exe。
3. 在“配置”页填写一次性显示的 Worker Token。发行包已内置生产 HTTPS 地址；普通界面不显示或编辑公网地址。
4. Worker 自动取得 Device ID；用户不需要填写 UUID。
5. Worker 自动检测 ShadowBot 6.3.6。自动检测失败时，可选择 ShadowBot.exe；其他版本会被拒绝。
6. 点击“测试连接”，确认服务器可达且 Token 有效后，点击“保存并启动”。
7. “本地输入”默认使用 %LOCALAPPDATA%\EcommerceAIWorker\data 下的 params.json、account.json 和 images；只有影刀应用要求其他固定路径时才需要修改。

升级已有 Worker
- 直接替换程序文件并双击 ecommerce-worker.exe。
- 自动复用 %LOCALAPPDATA%\EcommerceAIWorker\config.json 中原 Device ID、Server 和 DPAPI Token；升级不会覆盖已有 Server。
- 不会创建新的 Device UUID，也不要求重新签发 Token。

窗口与后台进程
- GUI 提供“状态 / 配置 / 诊断”三个页签。
- 最小化或关闭 GUI 会转入 Windows 托盘，不会停止后台 Worker Core；托盘可打开状态、打开日志或退出状态界面。
- 日常再次双击 ecommerce-worker.exe 可重新打开 GUI。
- 高级运维 CMD 入口继续保留，但普通首次配置不依赖 PowerShell。

ShadowBot 策略
- Worker 0.4.8 固定支持 ShadowBot 6.3.6。
- Task 图片会先下载并校验到配置的 images 目录，全部成功后才启动执行器。
- 当前会话、云端应用与执行均来自 6.3.6 本地会话接口。
- 若其他版本正在运行，Worker 不结束它，也不启动第二个版本，只报告版本不支持。

安全说明
- 每台设备必须使用独立 Worker Token。
- Backend 只保存 Token Hash；Token 明文仅在签发或轮换当次显示。
- Token 在本机使用 Windows DPAPI CurrentUser 加密，不写入明文 JSON、日志或 runtime-status.json。
- 生产环境必须使用 HTTPS。公网 HTTP 仅允许明确接受风险的临时开发验证。
- 本包不包含 SSH Key、数据库配置、店铺凭证或 Cookie。
- account.json 允许作为内部 V1 本地桥接保存明文 Account Payload；请把自定义路径放在受当前 Windows 用户保护的目录，禁止把内容复制到日志或任务结果。
- 0.4.7 引入、0.4.8 继续兼容的 Task Account Payload 会写入“店铺名称”；该字段仅来自当前 Task 关联店铺，不会授予全量店铺读取权限，也不写入日志。
- 使用新 Token 重新接入时，Worker 先停止空闲的旧 Core，才保存 Provisioning 返回的新 Device 身份并启动新 Core；任务运行中或旧 Core 无法停止时不会切换身份。

当前能力
- system.echo
- system.sleep
- yingdao.discover
- yingdao.app.run
- yingdao.test（仅显式配置无副作用测试应用时使用）

本版本不包含 Windows Service、自动更新、设备配对码或自动登录 ShadowBot。
