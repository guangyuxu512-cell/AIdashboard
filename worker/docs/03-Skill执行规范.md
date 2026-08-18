# Skill 执行规范

一个 Skill 表示一个明确可执行能力。

3B-Lite 只注册：

- `system.echo`
- `system.sleep`

统一进程输入：
- task_id
- params

统一输出：
- status
- result
- error_code
- error_message

Backend 只发送 `skill_id` 和参数。服务器不得发送 cmd、PowerShell、Python/EXE
路径或任意命令。Worker 必须先通过本地 Skill Registry 白名单和 Pydantic 输入
模型验证，再由 PythonExecutor 启动隔离子进程。

每个任务使用 `worker/runtime/<task_id>/`，保存 `input.json`、`output.json`、
`stdout.log` 和 `stderr.log`。已存在的同名运行目录不得被覆盖或删除。

`system.echo` 原样返回 message；`system.sleep` 接受大于 0 且不超过 300 秒的
seconds，用于 Lease/掉线测试。未来业务 Python 脚本仍通过新增稳定 skill_id 并在
本地 Registry 注册接入，不通过服务端传文件路径。
