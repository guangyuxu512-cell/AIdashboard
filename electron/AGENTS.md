# electron/AGENTS.md

## 1. 边界
Electron 是桌面 Host，不是业务后端，也不是 Worker。

负责：
- BrowserWindow
- App lifecycle
- Preload
- IPC
- 本地文件/目录
- 系统信息
- Worker 进程管理
- 打包升级

不负责：
- PostgreSQL
- 服务器业务规则
- 长期 Task Claim
- RPA 业务实现

## 2. 文档路由
先读 `electron/docs/00-文档索引.md`。

| 任务 | 必读 |
|---|---|
| Main/Window | 01 |
| IPC | 01 + 02 |
| Worker 启停 | 03 |
| 文件/系统能力 | 01 + 04 |
| 安全配置 | 04 |
| 打包/升级 | 05 |

## 3. 固定安全规则
必须：
- `contextIsolation = true`
- `nodeIntegration = false`
- Renderer 不直接 import `electron`
- Renderer 不直接 import `fs`
- Renderer 不直接 import `child_process`

统一链路：
```text
Renderer
↓
window.desktop typed API
↓
Preload
↓
IPC
↓
Main
↓
Service
```

## 4. IPC 禁止猜想
Channel 必须先查现有类型和 IPC 契约。
禁止随意创建字符串 Channel、同一能力多个命名、Renderer 直接使用 `ipcRenderer`。
新增 IPC 必须同步契约。

## 5. 抽象与第三方库
- 系统能力放 `services/`。
- IPC handler 不直接塞大量系统逻辑。
- 相同文件、进程、路径逻辑必须复用 Service。
- Node 标准库已有能力优先使用。
- 不引入第二套同类 Electron helper，除非现有能力无法满足。

## 6. Worker
Worker 必须作为独立进程。
Electron 只负责 start / stop / restart / getStatus。
Electron Renderer 不承载 Worker 长循环。

## 7. 最小权限
不因单一页面需求暴露高权限 IPC。
禁止暴露通用 `exec(command)`、任意文件读写等危险万能接口。
