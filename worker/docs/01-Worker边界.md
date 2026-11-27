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

店铺任务明确报告登录失效时，Worker 校验任务执行前后是否使用同一本机会话快照；确认后将店铺、版本和失败事实写入本机恢复队列，Worker 重启也可继续处理。商品管理的普通业务拒绝只触发限频身份复核，不作为失效证据。网络故障、平台业务拒绝、身份不匹配和无法解析均不触发登录。只有本地快照确实缺失，或该快照被明确判定登录失效时，Worker 才通知同机 RPA 刷新。正在执行的同店任务结束后再启动，同店后续任务等待 RPA 返回结果，其他店可继续；RPA 负责登录、同店校验及保存。新快照必须重新验证后才报告有效，旧快照的结果不能覆盖新快照。RPA 返回需要人工验证时停止重复尝试；其他暂时性故障按既有退避重试。状态上报暂时失败不影响本地恢复，任务结果仍按原有 Outbox 回传，不因刷新而自动重跑。

库存查询前后核对本机映射和快照；SQLite 临时不可读或映射持续变化时，有限重试后暂报设备库存不可用，保留上次观察并等待恢复，不判为登录失效。稳定库存按周期刷新；有未检查的店时每隔 5 秒轮到下一家，同店实际请求前后仍核对快照，正在刷新的店不会阻塞其他店检查。受信 RPA 的发现结果可复用，但每次启动助手前仍重新校验程序文件与授权指纹。

新业务以 Worker 执行的代码能力为目标。已有影刀任务暂为兼容保留，纯代码替代完成前不改变既有定时。

## Device 生命周期约束

Worker 不自行解释 Device.enabled。停用设备仍保持 Heartbeat 与 Provider Inventory 上报，用于让中控台看到真实运行状态，但 Backend 不会向其发放新 Task。软移除后旧 Token 对所有 Worker API 失效，Worker 应进入认证失败状态，不能自行复用旧 Device UUID。
