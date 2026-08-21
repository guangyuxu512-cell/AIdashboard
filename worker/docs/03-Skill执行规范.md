# Skill 执行规范

一个 Skill 表示一个明确、稳定的业务执行能力。

当前注册：

- `system.echo`
- `system.sleep`
- `yingdao.test`
- `yingdao.discover`

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
- Registry 明确 `runtime=python|rpa`。
- RPA Skill 额外声明 `provider=yingdao`，本地应用 ID 是设备侧映射。
- Backend 不得传影刀应用名称、CLI、文件路径或任意命令。

`yingdao.discover` 使用独立 `discovery` Runtime，只做本机影刀只读能力发现；它不经过 Python 子进程，也不启动影刀应用。当前 `yingdao.test` 已注册为 RPA/Yingdao 测试能力，但真实应用 ID 尚未获得正式
契约，因此生产映射为空，执行时明确失败而非猜测 App ID。

## SkillDescriptor

每个本地 `SkillDefinition` 同时提供稳定、可序列化的 `SkillDescriptor`：

- `skill_id`
- `display_name`
- `runtime`
- `provider`（无 Provider 时为 null）
- `version`

Descriptor 只描述 Worker 已实现能力，不暴露影刀 App ID、本地脚本路径或 EXE 路径。
本阶段不自动上报、不建立 Skill Inventory 表或 Skill Center；待首个真实业务 Skill 接入
时，再通过正式 Worker ↔ Backend 契约上报。
