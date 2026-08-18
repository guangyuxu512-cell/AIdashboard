# Worker 边界

3B-Lite 核心流程：
```text
读取 WORKER_SERVER_URL / WORKER_DEVICE_ID / WORKER_DEVICE_TOKEN
↓
Heartbeat
↓
每 3 秒 Poll / 原子 Claim 自身 Task
↓
按本地 Skill Registry 选择 PythonExecutor
↓
执行 Skill 并续租
↓
回传 complete / fail
```

Worker 只承担配置、Heartbeat、Poll、Claim、白名单 Skill 执行和结果回传六类职责。

Worker：

- 只主动访问 Backend，不监听本地 HTTP 端口。
- 不直接访问 PostgreSQL，不持有数据库账号。
- 不获取店铺密码、Cookie 或 Session Payload。
- 不承载 Vue/Electron UI。
- 不接受命令、Shell、脚本路径或 EXE 路径。
- 3B-Lite 只存在 PythonExecutor，不实现 RPA、Browser、Node 或 EXE Executor。
