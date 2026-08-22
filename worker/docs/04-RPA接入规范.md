# RPA 接入规范

RPA 是 Skill 的一种设备侧实现方式，不承担任务调度或服务器业务。

正式链路：

```text
Backend Task → Worker → RPAExecutor → YingdaoAdapter → 影刀
```

RPAExecutor 只负责确认 Provider、校验本地 App 映射、执行超时、统一 Result 转换
和 Runtime 收口。影刀应用执行细节只允许存在于 YingdaoAdapter；只读环境发现由
独立的 `YingdaoDiscoveryService` 承担，不能借 Discovery 启动应用。

必须支持：

- 外部启动与输入。
- 明确成功或失败。
- 超时退出。
- 结构化结果和稳定错误码。
- 日志与 Runtime 隔离。

统一运行目录：

```text
runtime/<task_id>/
├── input.json
├── status.json
├── output.json
├── stdout.log
├── stderr.log
└── artifacts/
```

## Yingdao Adapter Contract

Discovery 正式返回 provider、available、provider_version、logged_in、
account_display、account_type、enterprise_account、user_id、applications 与
discovered_at。每个 Application 只包含 `app_id`、`app_name`、`package_version`、
`entrypoint`，不包含密码、Token、Cookie 或完整认证响应。

## 已验证的只读 Discovery

`yingdao.discover` 是可重试的只读 Provider Inventory 发现能力，不属于影刀 App
执行。固定链路为：

```text
system health
→ 确认 console-restapi = ready
→ auth current
→ 使用响应中的 userId
→ %LOCALAPPDATA%/ShadowBot/users/<userId>/user.db3（SQLite read-only）
→ developmentsync_apps_v2 WHERE isRecycleBin = 0
→ apps/<appId>/xbot_robot/package.json
```

数据库只读取 uuid、name；package.json 只读取并校验 uuid、name、version、startup。
禁止扫描 users 目录猜测当前账号，禁止写入影刀数据库。任一 package 损坏会让本次
Discovery 以 `YINGDAO_PACKAGE_INVALID` 失败并指出 App ID，不会令 Worker 进程退出，
也不会静默丢弃应用。

当前已在 PersonalBasic 账号完成真实验证。个人账号的企业应用接口 5010 属于
not applicable，Discovery 不调用该接口，也不记录为系统错误。Enterprise 账号尚未
真实验证，不得宣称已支持。安装 Root 和可选数据 Root 进入 Worker Config，代码不
硬编码本机路径。

`developmentsync_apps_v2` 是设备本地同步缓存，不是账号云端完整应用索引。同一账号
在不同电脑上可能得到不同数量。排查这类差异时使用独立的影刀只读诊断包，只采集
当前账号的安全元数据、应用索引安全字段、包存在性和候选表结构；不得上传原始数据库、
Token、Cookie、变量、流程或选择器。未来完整列表与本机可执行状态必须作为两个维度
建模，不能继续用本地缓存数量代表账号云端应用总数。

诊断包通过 `scripts/build-yingdao-diagnostic.ps1` 构建为
`dist/yingdao-readonly-diagnostic-win-x64.zip`。目标电脑完整解压后只需双击
`影刀只读诊断.cmd`，再回传生成的 `yingdao-diagnostic.json`。

成功结果：

```json
{"status":"success","result":{}}
```

失败结果：

```json
{
  "status":"failed",
  "error_code":"RPA_EXECUTION_FAILED",
  "error_message":"..."
}
```

Discovery 与 Execution 是两个独立能力。Inventory 必须分别表达
`discovery_available`、`execution_available`、`execution_version` 和不可执行原因；
Discovery 成功不能推出 Execution 可用。

Discovery 版本策略：存在 6.3.9 CLI 时可以优先用于已验证的只读命令；没有时继续复用
当前 `auth current + userId + user.db3 + package.json` 本地发现链。Execution 只接受精确
白名单，禁止版本范围推断：

| 版本 | Discovery | Execution |
|---|---|---|
| 6.3.9 | CLI 存在时可用 | UNVERIFIED，禁止执行 |
| 6.3.6 | 现有 Discovery 链 | VERIFIED |
| 6.2.23 | 现有 Discovery 链 | VERIFIED |

执行优先级固定为 6.3.6、6.2.23。若只有 6.3.9，Discovery 可以 AVAILABLE，Execution
必须 UNAVAILABLE，并说明“当前影刀版本不在已验证执行白名单”。

真实启动只允许以 subprocess argument list、`shell=False` 的等价方式直接启动
`ShadowBot.exe`，第二个参数为按 URI 规则编码的
`shadowbot:Run?robot-uuid=<appUuid>&key=value`。这里禁止的是 cmd 的 `start ""`
包装形式，不是禁止直接启动 ShadowBot.exe。不得使用 StandaloneLauncher、UI 坐标点击、
未知 URI 变体或直接运行应用内部脚本。

同一 Worker 第一版同时最多执行一个影刀任务。启动前必须确认 App UUID 已在本机
Discovery Inventory 且 package 完整；云端存在但本机未同步时不得执行。Task 的成功
至少需要关联启动后产生的新 tasklog、匹配目标 App 的真实 started 记录和真实 exited
记录。启动进程退出或 tasklog 文件存在都不等于成功；失败规则只能来自已验证样本。
没有安全停止入口时，超时不得杀掉整个 ShadowBot.exe。

RuntimeYingdaoAdapter 通过 Worker Runtime Event Bus 上报状态和 tasklog 增量日志，
Provider 不直接请求 Backend。默认发行配置不映射任何真实 App；只有显式配置并经人工
确认无副作用的测试 App 才能进入真实 Run，业务 App 禁止作为工程验证对象。

禁止：

- Backend 直接操作影刀或执行电脑文件。
- RPA 自己轮询中控台或访问 PostgreSQL。
- RPA 硬编码账号密码、Cookie 或 Token。
- Backend Task 直接绑定影刀应用名称。
- 错误后无状态退出或无限等待人工输入。

浏览器 Profile 与 Credential/Session 下发不属于本阶段。
