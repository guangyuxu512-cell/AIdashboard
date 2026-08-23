# Skill 执行规范

一个 Skill 表示一个明确、稳定的执行能力。`classification` 只分为：

- `internal`：Worker 基础设施、测试或 Provider 运行能力；
- `business`：用户实际部署的业务脚本能力。

当前 `system.echo`、`system.sleep`、`yingdao.app.run`、`yingdao.test`、
`yingdao.discover` 均为 `internal`。分类必须在 Registry 定义处显式声明，不根据
`skill_id` 前缀推断。`SkillDefinition` 默认分类为 `business`，新增 `refund.sync` 等
业务脚本时应保留或显式确认该分类；Worker 内置能力必须显式改为 `internal`。

当前注册：

- `system.echo`
- `system.sleep`
- `yingdao.test`
- `yingdao.discover`
- `yingdao.app.run`

统一输入：

- task_id
- skill_id
- params

统一输出：

- status
- result
- error_code
- error_message

Backend 只发送 `skill_id` 和参数。服务器不得发送 cmd、PowerShell、Python/EXE
路径或任意命令。Worker 必须先通过本地 Skill Registry 白名单和 Pydantic 输入
模型验证，再按 `runtime` 路由到 PythonExecutor 或 RPAExecutor。

每个任务统一使用 `worker/runtime/<task_id>/`：

```text
input.json
status.json
output.json
stdout.log
stderr.log
artifacts/
```

`input.json` 包含 `task_id`、`skill_id`、`params`。已存在的同名运行目录不得被
覆盖或删除。

`system.echo` 原样返回 message；`system.sleep` 接受大于 0 且不超过 300 秒的
seconds。未来业务 Python 脚本仍通过新增稳定 skill_id 并在本地 Registry 注册，
不通过服务端传文件路径。

## Skill、Executor 与 Provider

```text
Task → stable skill_id → Skill Registry → runtime → Executor → Provider
```

- Skill 是稳定业务能力，不等于影刀 App。
- Registry 明确 `runtime=python|rpa|discovery`。
- Provider Skill 通过 Descriptor 声明 `provider=yingdao`；影刀 Application 由
  `yingdao.app.run` 的 `input.app_id` 选择，不是 Skill，也不是设备侧固定映射。
- Backend 不得传影刀应用名称、CLI、文件路径或任意命令。

`yingdao.discover` 使用独立 `discovery` Runtime，负责当前 6.3.6 会话与云端应用能力发现；它不经过 Python 子进程，也不启动业务应用。`yingdao.app.run` 是稳定的通用影刀应用执行 Skill，输入只允许 `app_id + params`；它不为每个 App 动态注册 Skill，也不接受可执行文件或命令路径。当前 `yingdao.test` 仅保留兼容测试能力。
契约，因此默认映射为空，执行时明确失败而非猜测 App ID。只有负责人明确确认无副作用的测试 App，才允许通过 Worker Config 显式建立设备侧映射。

Skill 只负责校验输入、执行、发出进度/日志和返回结果。Skill、脚本或 RPA 不得自行负责 Heartbeat、Poll、Worker Token、Backend Task 领取、Cookie 管理或 Backend 状态回传；Python、Browser、EXE 等后续 Executor 必须复用 Worker Runtime Event Bus。

## SkillDescriptor

每个本地 `SkillDefinition` 同时提供稳定、可序列化的 `SkillDescriptor`：

- `skill_id`
- `display_name`
- `runtime`
- `provider`（无 Provider 时为 null）
- `version`
- `classification`（`internal | business`）

Descriptor 只描述 Worker 已实现能力，不暴露影刀 App ID、本地脚本路径或 EXE 路径。
Worker 在启动后的首次成功 Heartbeat 以及断线重连后，将当前 Registry 的完整 Descriptor
快照上报到 `PUT /api/v1/worker/skill-capabilities`。请求不接受 `device_id`，设备身份只来自
既有 Worker Token 与 `X-Device-ID`。Backend 使用 snapshot replace 同步当前 Device × Skill：
Registry 中已删除的 Skill 会在下一次同步移除；设备 OFFLINE 时保留最后一次已知能力。

Skill Capability 表达“该 Worker 已实现此 Skill”，不表达当前任务状态，也不替代 Provider
Inventory。Provider Capability、Skill Capability 与 Provider Application 必须保持三层独立。
Worker 始终上报 `internal + business` 的完整快照；分类只影响普通业务界面的统计与展示，
不得影响 Task Guard 按 `(device_id, skill_id)` 判断执行资格。未来 Python 业务 Skill 仍通过本地
Registry 注册为 `business` 并进入同一快照，不引入在线安装或 Skill CRUD。
