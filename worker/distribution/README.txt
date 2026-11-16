Ecommerce Worker 0.5.7 for Windows
=================================

此程序连接中控并执行设备任务；中控网页与独立商品库是不同入口。
Worker 从本机 RPA 保存的店铺资料读取 Session，不要求保持浏览器窗口打开。
请使用与 RPA 相同的 Windows 用户运行 Worker。店铺信息保留在本机。

首次接入
1. 在中控设备中心为本机签发 Worker Token。
2. 解压发行包并运行 ecommerce-worker.exe，在配置中输入 Token。
3. 测试连接并启动；设备身份由中控返回，不需要手填设备编号。

升级已有 Worker
- 等当前任务结束，停止旧 Worker，再从新目录启动新版。
- 新版沿用当前 Windows 用户的设备身份和受保护配置，不清空 RPA 店铺资料。
- Worker 底座与已签名能力包分别更新；能力包可由 Worker 自动获取。

商品库预检由中控调度，结果直接回传独立商品库。登录状态明确失效时跳过该店；
网络、权限和平台风控错误不直接判定为登录失效。

安全
- 每台设备使用独立 Worker Token，Token 在本机使用 Windows DPAPI 保护。
- 发行包不包含数据库凭据、店铺 Session 或 Cookie。
- 保留旧版配置目录；不要在任务运行中替换 Worker。
