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

普通用户的正式接入流程只使用中控台和 Worker GUI：

1. 在中控台创建 Device。
2. 在 Device Drawer 的“Worker 凭证”区域签发独立 Token；明文只在该次 Dialog 显示，立即复制到目标电脑。
3. 将通用 ZIP 复制到目标 Windows 电脑并解压；不要复制服务器 SSH Key、项目源码或其他设备配置。
4. 双击 ZIP 根目录的 `ecommerce-worker.exe`。没有有效配置时程序自动打开“配置”页，不启动无限失败重试。
5. 输入 Backend HTTPS URL 和 Worker Token。GUI 通过 Token 解析只读 Device ID/设备名称，用户不得手填 UUID。
6. GUI 复用正式 `WindowsYingdaoRuntimeLocator` 自动检测 ShadowBot 6.3.6；自动检测失败时才选择 `ShadowBot.exe`，且必须通过精确版本校验。
7. 点击“测试连接”，确认服务器可达且 Token 有效；点击“保存并启动”后，配置由正式 Config Service 保存并启动长期运行的 Worker Core。
8. Worker 上线后自动 Heartbeat、同步 Skill Capability 并刷新 Yingdao Provider。

普通接入不要求 PowerShell、编辑 JSON 或首次配置 CMD。发行包保留 CMD/PowerShell 入口仅供高级运维与兼容，不作为产品主流程。公网 Server URL 应使用 HTTPS；负责人明确批准的可丢弃开发服务器可临时使用 HTTP，但 Token 和任务流量没有传输加密，切换 HTTPS 后必须轮换曾通过 HTTP 使用的 Token。

## 配置与本地数据

```text
%LOCALAPPDATA%\EcommerceAIWorker\
├── config.json
├── worker-state.json
├── logs\
└── runtime\<task_id>\
```

目录位于当前 Windows 用户的 LocalAppData。GUI 与 Worker Core 共用同一个正式 Config Service 和同一份 `config.json`，不建立第二套 GUI 配置源。Token 使用 Windows DPAPI `CurrentUser` 加密后写入配置，明文不得进入 JSON、日志、`worker-state.json` 或 `runtime-status.json`。非敏感配置使用临时文件、flush/fsync、关闭后原子替换，避免运行中保存产生半文件。日志按 5 MiB、5 个备份轮转；Runtime 不写入发行包或 Program Files。

影刀本地数据根目录只用于读取实际运行产生的 `task_logs`，不再用于识别账号或云端应用；默认是启动 Worker 的 `%LOCALAPPDATA%\ShadowBot`。

Worker 0.4.1 的正式 Provider 与 Execution 版本固定为影刀 6.3.6，不自动选择或回退 6.2.23、6.3.9 等其他版本。Locator 依次复用当前配置、当前运行中的 6.3.6、安装注册信息与系统候选位置；手工选择也必须验证真实文件版本等于 6.3.6。其他版本目录可以继续存在；若其他版本正在运行，Worker 不结束它，也不启动第二实例，只上报版本不支持。0.4.1 会在启动与断线重连后同步带 `internal | business` 分类的完整 Skill Registry 快照，并兼容当前会话 API 已真实观察到的 `Code/Data` 与 `code/data` Envelope。

当前账号由 6.3.6 的 `/api/v1/account/current` 唯一确定，不需要从多个 `user.db3` 缓存中手工选择 userId。

## Worker GUI 与日常控制

`ecommerce-worker.exe` 默认打开现有 Tkinter GUI：

- 状态：设备、Device ID、Worker/服务器状态、ShadowBot 状态/版本/账号/应用数、Skill 同步、当前任务、运行时间与最近脱敏日志。
- 配置：Backend 地址、默认掩码的 Worker Token、只读设备身份和 ShadowBot 6.3.6 路径；支持测试连接、自动检测、严格手工选择和保存重连。
- 诊断：Backend、Token、Heartbeat、Skill 同步、ShadowBot 进程/版本/Session、应用数与最近 Provider 刷新；只提供重新检测和打开日志目录。

GUI 只是本机配置与观察入口，不是 Worker Core 的运行前提。已有有效配置时 GUI 会确保 Core 已启动；关闭 GUI 后 Core 继续后台运行。Core 通过不含 Token 的 `worker-state.json` 记录 PID、启动时间、EXE 路径和 Device ID，用于精确识别与停止。

- `启动Worker.cmd`：检查配置和精确进程身份；已有实例时不重复启动，随后显示进程、Backend、Device ID、Server URL 与 Device Runtime。
- `打开Worker状态.cmd`：打开同一个 Tkinter 状态/配置/诊断窗口；关闭窗口不影响后台 Worker。
- `停止Worker.cmd`：使用状态文件中的 PID、启动时间和 EXE 绝对路径三重校验，只停止本 Worker。
- `查看状态.cmd`：只读显示运行与连接状态，不显示 Token、Credential 或 Cookie；影刀账号的权威结果以中控台设备能力为准，不在控制脚本中伪造已登录状态。
- `配置影刀并重启.cmd`：保留 Device ID 与 Token，只在自动发现失败时覆盖影刀安装根目录或 tasklog 数据根目录，然后重启 Worker。
- `首次配置并启动-开发HTTP.cmd`：显式允许临时公网 HTTP，只用于已批准的可丢弃开发环境。

Worker 进程另以 `Global\\EcommerceAIWorker-<device_id>` Windows Mutex 保证同一电脑同一 Device 单实例，即使绕过控制脚本直接启动第二个 EXE，也会退出。

## 当前发行能力

- `system.echo`
- `system.sleep`
- `yingdao.discover`（通过 6.3.6 当前会话刷新账号与云端应用 Inventory）
- `yingdao.app.run`（按 App ID 和经 Backend Schema 校验后的参数创建真实影刀运行）

PyInstaller 冻结环境中的 Python Skill 通过同一 EXE 的内部 `--skill-runner` 入口执行，Backend 仍只能下发已注册 Skill ID，不能下发任意命令或路径。影刀运行继续通过现有 Task、Lease、Runtime Event 与 tasklog 链完成；当前不提供 Windows Service、自动更新、浏览器登录或动态 Skill 下载。

## 掉线与恢复

停止 Worker 后，Backend 根据 Heartbeat 超时把 Device 标记为 OFFLINE；再次双击 Worker EXE 或使用高级启动入口时，程序读取原有 0.3.2 配置、复用同一 Device ID，并用 DPAPI 解密原 Token 恢复 ONLINE，无需重新签发。轮换后旧 Token 立即失效，撤销后 Heartbeat/Poll/Capability Sync 都认证失败；此时必须在中控台重新签发或轮换，并在 GUI 更新 Token。升级不得创建新 Device UUID。
