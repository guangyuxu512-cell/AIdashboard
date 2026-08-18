# Worker 安装与设备接入

## 网络前提

执行电脑只需要能够主动访问 Backend。Backend 不会连接执行电脑的本机端口，
因此家里电脑、公司电脑、NAT 网络和动态 IP 均不要求公网 IP、端口映射或入站规则。

## 最小接入流程

1. 将同一份 `worker` 代码复制或安装到目标 Windows 电脑。
2. 在 `worker` 目录创建 Python 3.12 虚拟环境，并执行
   `python -m pip install -e ".[dev]"`。
3. 在中控台创建一条 Device，记录稳定的 `device_id`。
4. 在 Backend 目录执行
   `python -m app.cli.worker_token issue <device_id>`。Token 明文只显示一次，
   不要写入日志或提交 Git。
5. 复制 `.env.example` 为 `.env`，配置：

   ```text
   WORKER_SERVER_URL=https://可访问的中控Backend地址
   WORKER_DEVICE_ID=<device_id>
   WORKER_DEVICE_TOKEN=<一次性输出的token>
   ```

6. 在 Worker 虚拟环境运行 `python -m app`。
7. Heartbeat 成功后，Device Center 会显示 Worker ONLINE、版本和最近心跳。

每台电脑必须使用不同 Device Identity 和独立 Token。同一个 Token 不得在多台电脑
共用。需要轮换或停用时，分别执行 CLI 的 `rotate` 或 `disable` 子命令。

## 安全边界

Worker `.env` 不提交 Git。Worker 不配置 `DATABASE_URL`，也不接收店铺密码、
Cookie、Session Payload、Shell 命令或本地程序路径。当前只可执行本地注册的
`system.echo` 与 `system.sleep`。
