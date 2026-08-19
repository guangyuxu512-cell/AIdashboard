# Worker 安装与设备接入

## 网络边界

执行电脑只主动访问 Backend HTTPS，不需要公网 IP、端口映射、入站规则、SSH Key、Backend、PostgreSQL 或完整项目源码。Backend 不主动连接执行电脑，Worker 不访问 PostgreSQL。每台电脑必须使用独立 `device_id` 和 Device Token。

## 构建发行包

开发机在项目根目录执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\build-worker.ps1
```

脚本依次 clean、pytest、PyInstaller `onedir`、组装并生成：

```text
dist/ecommerce-worker-<version>-win-x64.zip
```

通用 ZIP 只包含 Worker EXE/runtime、控制脚本、README 和版本文件；不包含 Frontend、Electron、Backend、tests、Python 开发虚拟环境、数据库配置、SSH Key、Device ID、Device Token、Credential 或 Cookie。

## 第二台电脑首次接入

1. 在中控台创建 Device，记录稳定 `device_id`。
2. 开发者在 Backend 环境执行 `python -m app.cli.worker_token issue <device_id>`，Token 明文只出现一次。
3. 将通用 ZIP 复制到目标 Windows 电脑并解压；不要复制服务器 SSH Key。
4. 双击 `首次配置并启动.cmd`。
5. 输入 Backend HTTPS URL、Device ID、Device Token；本机装有影刀时可填写 ShadowBot 安装根目录。
6. 脚本验证配置、加密保存 Token、后台启动 Worker，并显示 Backend 与设备连接状态。

公网 Server URL 默认强制使用 HTTPS。仓库不提供 localhost 默认值；明文 loopback 只允许构建验证显式启用。对于负责人明确批准的可丢弃 DEV 服务器，可改用 `首次配置并启动-开发HTTP.cmd`，但该入口会警告 Token 和任务流量没有传输加密，绝不能用于正式服务器或重要数据。切换 HTTPS 后必须轮换曾通过 HTTP 使用的 Token。

## 配置与本地数据

```text
%LOCALAPPDATA%\EcommerceAIWorker\
├── config.json
├── worker-state.json
├── logs\
└── runtime\<task_id>\
```

目录 ACL 限制为当前 Windows 用户。Token 使用 Windows DPAPI `CurrentUser` 加密，控制脚本和状态输出都不打印 Token。日志按 5 MiB、5 个备份轮转；Runtime 不写入发行包或 Program Files。

## 日常控制

- `启动Worker.cmd`：检查配置和精确进程身份；已有实例时不重复启动，随后显示进程、Backend、Device ID、Server URL 与 Device Runtime。
- `停止Worker.cmd`：使用状态文件中的 PID、启动时间和 EXE 绝对路径三重校验，只停止本 Worker。
- `查看状态.cmd`：只读显示运行与连接状态，不显示 Token、Credential 或 Cookie。
- `首次配置并启动-开发HTTP.cmd`：显式允许临时公网 HTTP，只用于已批准的可丢弃开发环境。

Worker 进程另以 `Global\\EcommerceAIWorker-<device_id>` Windows Mutex 保证同一电脑同一 Device 单实例，即使绕过控制脚本直接启动第二个 EXE，也会退出。

## 当前发行能力

- `system.echo`
- `system.sleep`
- `yingdao.discover`（本机已安装并登录影刀时执行只读 Inventory 发现）

PyInstaller 冻结环境中的 Python Skill 通过同一 EXE 的内部 `--skill-runner` 入口执行，Backend 仍只能下发已注册 Skill ID，不能下发任意命令或路径。当前不提供 Windows Service、自动更新、真实影刀 App 执行、浏览器登录或动态 Skill 下载。

## 掉线与恢复

停止 Worker 后，Backend 根据 Heartbeat 超时把 Device 标记为 OFFLINE；再次运行 `启动Worker.cmd` 后使用 DPAPI 解密原 Token 并恢复 ONLINE，无需重新签发。只有 Token 被 rotate、disable 或泄露时才需要重新配置。
