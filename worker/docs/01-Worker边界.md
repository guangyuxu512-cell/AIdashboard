# Worker 边界

3B-Lite 核心流程：
```text
读取 WORKER_SERVER_URL / WORKER_DEVICE_ID / WORKER_DEVICE_TOKEN
↓
Heartbeat
↓
每 3 秒 Poll / 原子 Claim 自身 Task
↓
按本地 Skill Registry 选择 PythonExecutor / RPAExecutor
↓
执行 Skill 并续租
↓
回传 complete / fail
```

Worker 只承担配置、Heartbeat、Poll、Claim、白名单 Skill 执行和结果回传六类职责。

Worker：

- 只主动访问 Backend，不监听本地 HTTP 端口。
- 不直接访问 PostgreSQL，不持有数据库账号。
- 店铺状态验证通过受信任的本机 RPA 桥读取已保存会话，状态上报不包含会话内容。自动补取只向同机受信 RPA 发送固定店铺与快照标识，由 RPA 使用对应比特窗口完成，不接受服务器指定程序路径。现行类目预检为服务器签名临时发送本店 Cookie，再由 Worker 在本机请求平台。
- 不承载 Vue/Electron UI。
- 不接受命令、Shell、脚本路径或 EXE 路径。
- 当前存在 PythonExecutor 与 RPAExecutor；Browser、Node、EXE Executor 尚未实现。

新业务以 Worker 执行的代码能力为目标。已有影刀任务暂为兼容保留，纯代码替代完成前不改变既有定时。

## Device 生命周期约束

Worker 不自行解释 Device.enabled。停用设备仍保持 Heartbeat 与 Provider Inventory 上报，用于让中控台看到真实运行状态，但 Backend 不会向其发放新 Task。软移除后旧 Token 对所有 Worker API 失效，Worker 应进入认证失败状态，不能自行复用旧 Device UUID。
