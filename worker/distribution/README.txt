Ecommerce AI Worker for Windows
================================

首次接入
1. 在中控台创建独立 Device，并由 Backend CLI 为该 Device 签发一次性 Token。
2. 双击“首次配置并启动.cmd”。
3. 输入 Backend HTTPS URL、Device ID、Device Token。
4. 影刀路径通常留空，由 Worker 自动发现/启动 6.3.6；自动发现失败时才填写安装根目录覆盖。
5. 本地数据根目录只用于 tasklog，默认留空使用当前 Windows 用户目录。

当前影刀策略
- Worker 0.3.0 固定使用影刀 6.3.6，不自动选择或回退其他版本。
- 其他版本可以留在磁盘；若其他版本正在运行，Worker 不结束它，也不启动第二实例。
- 当前账号和云端应用来自 6.3.6 当前会话接口，不读取多个 user.db3 缓存作判断。
- 该入口保留已有 Device ID 和加密 Token，不要求重新输入 Token。

临时开发HTTP
- 仅在负责人明确接受明文风险时，使用“首次配置并启动-开发HTTP.cmd”。
- HTTP 会让 Device Token 和任务流量失去传输加密，不得用于正式服务器或重要数据。

日常使用
- 启动Worker.cmd：检查配置和现有实例后在后台启动。
- 停止Worker.cmd：只停止状态文件精确记录的本 Worker PID。
- 查看状态.cmd：显示进程、Backend、Device ID、Server URL 和设备连接状态。
- 打开Worker状态.cmd：只读显示当前任务、执行阶段和最近运行日志；关闭窗口不影响后台Worker。
- 配置影刀并重启.cmd：单独更新影刀路径覆盖，不改变设备身份。

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
- yingdao.app.run（运行当前账号可访问的云端应用；参数由中控台配置）
- yingdao.test（仅在显式配置无副作用测试App UUID，并且存在已验证执行版本时可用）

不包含 Windows Service、自动更新或浏览器登录。
