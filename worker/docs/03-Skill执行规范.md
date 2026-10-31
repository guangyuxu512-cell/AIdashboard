# Skill 执行规范

## 商品预检开发候选

`product.precheck` 尚未注册到生产 Registry。本候选为 Worker Task 和 Skill Context 增加可选的
有序非秘密 `shop_ids`；旧任务和原 `accounts` 不变。Python Executor 的 input.json 仍只存普通参数、
账号契约和非秘密店铺 ID，禁止存入预检 Session。Worker 客户端提供仅 HTTPS 的任务会话读取，返回值中的
Cookie 使用 SecretStr 且不写日志；此方法尚未接入运行中的 Skill。Worker 父进程到 Skill 的安全会话桥、商品云库批次
读取/结果回写以及抖店类目/属性适配尚未实现。

`app.skills.product_precheck.batch` 将每件带修订标识的商品仅分配给一家店铺，保持每店队列顺序与
结果原顺序，显式限制单店 1–5 和总并发 1–25。100 件/5 店可得到每店 20 件；每店 5、总计 25 只是
可配置上限，首次真实验证须从较低并发开始，依据平台反馈调整。单项异常返回固定安全错误码并继续；
回调返回仅表示函数已完成，不等于平台预检成功，最终分类及详细安全诊断由平台适配器负责。

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

`input.json` 是 Worker 控制的子进程输入。Python Runtime 在原有 `task_id`、`skill_id`、
`params` 之外还携带有序 `accounts` 与 `paths.images`，但 Business Skill 只能通过已校验的
Pydantic Input 和 `SkillContext` 消费这些值；不得自行读取该内部文件。已存在的同名运行目录
不得被覆盖或删除。

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

## Worker Local Input Bridge V1

外部影刀 Application 无法直接消费 Worker Python 对象，因此统一通过 Worker 配置的三个固定
本地落点桥接：

```text
Yingdao Task input.params → params.json
Task Account Payload      → account.json
图片                       → images 目录
```

默认落点位于 `%LOCALAPPDATA%\EcommerceAIWorker\data\`，也可在 Worker GUI 的“本地输入”
区域修改。每次 `yingdao.app.run` 真正启动 Application 前，RPAExecutor 必须先完整覆盖
`params.json`，再完整覆盖 `account.json`，并确认图片目录存在且可写。两个 JSON 都使用 UTF-8、
中文不转义和原子替换；无参数写 `{}`，`account.json` 根对象固定为 `店铺列表`，无 Account
Payload 时写 `{"店铺列表":[]}`，绝不合并或保留上一个 Task 的字段。任一步失败时 Task 以安全
错误结束，且不得调用 ShadowBot Run。

Local Input Bridge 只是跨进程输入适配，不替代现有 ShadowBot Application Params；现有 URI
参数仍继续传递。Backend 在认证 Claim 时按 Task 的有序 Shop 关系构建 `accounts`，每项内部字段
固定为 `shop_id / shop_name / platform_code / login_identifier / secret /
preferred_verification_channel`，不包含 Cookie/Session 或验证码挑战，也不进入 Task Input、日志、
Runtime Event 或 Result。RPAExecutor 仅在落盘边界映射为 `店铺ID / 店铺名称 / 平台编码 / 登录账号 /
登录密码 / 首选验证方式` 并一次完整覆盖 `account.json`；不得同时写英文重复字段。Python
Business Skill 通过英文 `ctx.accounts` 读取。

`shop_name` 是 0.4.7 增加的可选字段，名称仅来自该 Task 已关联的 Shop 记录，保持 Task 原有
Shop 顺序，并不授权 Worker 读取全量店铺。Backend 仅在 DeviceRuntime 报告 0.4.7 或更高版本时
在 Claim 中下发该字段；旧版或未知版本收到原字段集合，以兼容旧 Worker 的 `extra="forbid"`。
新 Worker 对没有 `shop_name` 的旧 Backend Claim 保持兼容。推荐顺序是先发布兼容 Backend，再在当前
Task 结束后升级 Windows 包；不要求强制重启或替换正在执行的 Worker。

Worker 0.4.7 的 Task Claim 可以携带有序图片清单。统一 Task 图片准备阶段位于 Executor 之前：
先读取受管文件 Manifest 并只清理上一 Task 由 Worker 写入的文件，再按 position 通过认证 Worker
API 下载本 Task 图片，校验字节数与 SHA-256，并使用原子写入落到固定 images 目录。同名文件按
稳定的 `__2`、`__3` 后缀分配，不覆盖同一 Task 的另一张图片。无图片 Task 也会清理上一集合；
手工放入且不在受管 Manifest 中的文件不会被删除。任一下载、Hash、写入或 Manifest 失败均在
Executor 前返回安全错误，影刀和 Python Skill都不会启动。图片目录仍禁止配置为磁盘根目录。

固定文件依赖当前 Worker 单 Active Task 边界。GUI 在 Task RUNNING 时不允许保存并重启配置，
因此已启动任务不会中途切换路径；任务结束后保存配置并重启，后续 Task 使用新路径。未来若允许
同一 Worker 并行多个 Local Bridge Task，必须先升级 task-specific workspace，本阶段不得提前实现。

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

## Internal Business Skill SDK V1

SDK 位于 `app/skills/sdk/`，是 Worker 仓库内部开发接口，不是独立 pip 包。Python Business
Skill 的唯一执行链为：

```text
Task
→ PythonExecutor（隔离子进程、超时、Runtime目录）
→ BusinessSkillRunner（Input校验、Context、Result/Error映射）
→ BusinessSkill.run()
→ ExecutionResult
→ 现有Task Runtime
```

SDK 继续复用现有 `SkillDescriptor` 与 `SkillDefinition`，不建立 V2 Descriptor。一个 Python
Business Skill 由以下轻量 Contract 组成：

- `descriptor`：`skill_id/display_name/runtime/provider/version/classification`；
- `input_model`：必须继承 `BusinessSkillInput`；
- `timeout_seconds`：大于 0；
- `async run(ctx, input) -> SkillResult`。

`register_business_skill(registry, skill)` 是唯一注册入口。它会校验 `classification=business`、
`runtime=python`、异步 `run()`、结构化 Input 以及稳定 Skill ID。V1 Python Business Skill 不拥有
RPA Provider；需要影刀时仍使用已有 Internal Provider Skill/Task Contract。新增正式 Skill 时只需
新增实现模块，并在 Worker 的单一 Skill 装配入口调用一次注册函数；Capability Snapshot 与 Backend
Device × Skill 同步无需 Frontend/Backend 硬编码。

### Business Skill Catalog Contract

Business Skill 的 Pydantic `input_model` 是输入 Contract 唯一 Source of Truth。注册时由
`model_json_schema(mode="validation")` 生成 JSON Schema，并随完整 Skill Capability Snapshot
上报；禁止为 Scheduler、Frontend 或未来 AI Agent 再维护一份手写参数定义。Schema 只描述输入，
不能替代 Worker 在执行前的 Pydantic 最终校验。

V1 对外 Catalog 支持 `string / integer / number / boolean / enum` 以及
`required / default / title / description`。复杂对象、数组和无法安全解释的组合 Schema 会被
Backend 明确标记为不支持，不能静默渲染。单个 Input Schema 的紧凑 JSON 大小上限为 32 KiB；
超过上限时 Business Skill 注册失败，防止无限元数据进入 Capability Snapshot。

Worker 仍上报 `internal + business` 完整快照，但普通 Business Skill Catalog 只消费
`classification=business`。旧 Worker 没有 `input_schema` 时保持兼容，Backend 记录最后已知能力并
标记 Schema unavailable；Scheduler 不得据此猜参数或开放配置。

Business Skill ID 使用小写点分业务语义，例如 `refund.sync`、`order.sync`、
`product.check_stock`。禁止文件名、临时版本号、连字符脚本名和无业务含义编号；`.py` 后缀不是
Skill ID 的一部分。`skill_id` 是手工 Task、未来 Scheduler、飞书触发和 AI Agent 共同引用的
长期 Contract。

### Input

Input 使用 Pydantic，并继承默认 `extra=forbid` 的 `BusinessSkillInput`。Worker 在进入 `run()` 前
完成最终校验；缺必填、类型错误或额外字段统一返回 `SKILL_INPUT_INVALID`。Skill 不得使用
`**kwargs`、环境变量、全局 JSON 或 Frontend 字符串猜参数。Backend Skill Catalog 提前暴露由
同一 Input Model 生成的 Schema，但不会替代 Worker 运行边界校验。

### SkillContext

V1 Context 只暴露真实能力：

- `task_id / device_id / skill_id`；
- `timeout_seconds / deadline`；
- `accounts`：当前 Task 的有序只读 Account Payload 列表；没有正式 Payload 时为空列表；
- `paths.images`：Worker 配置的固定图片工作目录；
- `is_cancelled`：仅表示本地 Runner 的协作式取消/超时状态；当前没有 Backend Cancel Contract；
- `log(message, level, metadata)`；
- `progress(current, total?, message?)`。

普通业务参数的唯一入口仍是 `run(ctx, input)` 中已通过 Pydantic 校验的 `input`。Python
Business Skill 禁止读取固定 `params.json`，也不暴露 `ctx.paths.params_json`。账号 Payload
不得被完整写入日志、Runtime Event 或 Result。

`ctx.log()` 与 `ctx.progress()` 先进入子进程内的 Runtime Event Bus，再经本地事件桥交回父进程
已有 Runtime Event Bus，最终复用 EventBuffer、批次、重试、脱敏、Backend Task Events 和
TaskRuntimeDrawer。业务代码不得直接请求 Event API，也不得管理 task_id、seq、event_at 或重试。
日志、进度和最终结果是三个独立语义。

V1 不实现 `resources`、通用 Backend Client、Domain Gateway 或 Auth Context。后续确有业务需要
时由 `SkillContext` 增加正式 Gateway；Business Skill 仍不得拼接 Backend URL/Token、直连
PostgreSQL、读取数据库 Credential 或自行下发 Cookie。Resource Manager、资料仓、Session 下发
与 Artifact 另立阶段，不虚构 Task Input Contract。

### Result 与 Error

成功必须返回：

```python
SkillResult(
    summary="退款同步完成",
    data={"fetched": 1023, "created": 200, "updated": 823},
)
```

`summary + data` 必须是 JSON 可序列化的小结果，总大小最多 64 KiB。禁止返回成千上万条业务
记录、图片、完整 Excel 或其他大对象；业务明细应写入未来对应 Backend 领域模块，文件走未来
Artifact/Resource Contract。

可预期业务失败抛出 `SkillExecutionError(code, message, retryable, details?)`。`code` 使用稳定大写
下划线格式；`message` 必须是用户安全摘要；`retryable` 目前进入运行事件诊断，不会触发 Worker
自动重试；`details` 默认不上传，且只能包含明确安全信息。普通 Exception 被 Runner 转换为
`SKILL_EXECUTION_FAILED`，Task 只收到安全摘要；Worker 本地日志仅记录异常类型与不含异常文本的
调用栈位置，避免 Token/Cookie/Credential 泄漏。

Task 状态映射保持不变：`SkillResult → SUCCESS`，`SkillExecutionError/输入失败/未知异常/超时
→ FAILED`。Runner 不新增 `PARTIAL/RETRYING/CANCELLED`。PythonExecutor 仍使用隔离子进程；
Runner 的协作式超时先尝试取消异步 Skill，父进程超时边界仍可结束失去响应的 Skill 进程。
SDK 自动复用 PythonExecutor 已有 started Status 和 Worker 的 completed/failed 终态事件，不重复
制造第二组生命周期事件。

### 开发模板与 Production Registry

模板在 `examples/demo_progress_skill.py`，展示 Input、Descriptor、Business classification、
`run()`、`ctx.log()`、`ctx.progress()`、`SkillResult` 和 `SkillExecutionError`。模板没有导入
Production `app.skills` 装配入口，也没有注册副作用，因此正式 Worker 当前 Business Skill 仍为 0。

## Task Queue 与 Executor/Provider 并发

Backend Queue 中可以同时存在多个 PENDING Task；Queue 深度与 Worker Execution Slot 是不同概念。
当前 Worker Core 的主循环一次 Claim 一个 Task，并等待其 Terminal 后才继续 Poll，因此总体实现
仍是单活动 Task。这个现有限制没有写入 SDK：Business Skill 不得假设永远只有一个 Task，所有
Context 与 Runtime 状态都必须按 `task_id` 隔离。

Yingdao Provider V1 的 execution capacity 固定为 1。RPAExecutor 使用 Provider 级 Semaphore，
ShadowBot Adapter 保留自身互斥作为防御层。Skill 内部不得通过 sleep/poll 等待槽。正常情况下，
当前单活动 Task 主循环使后续影刀 Task 保持 Backend PENDING；前一 Task SUCCESS 或 FAILED 后释放
槽并继续下一项。若 Task 已超时但底层影刀调用尚未真正返回，RPAExecutor 返回 FAILED 的同时继续
占用 Provider 槽；`can_claim()` 暂停新 Claim，直到真实调用退出并完成 cleanup，避免盲目启动第二个
ShadowBot Application。

当前 Backend Claim API 不能按 Runtime/Provider 选择候选 Task，所以“超时但 Provider 仍活动”
期间会保守暂停所有新 Claim，包括 Python。未来若开放 Worker 多 Executor 并发，必须先建立
slot-aware Claim/调度契约，使 Yingdao capacity=1 不限制独立 Python capacity；禁止简单删除
Provider 槽或改成全局永久锁。Worker 进程崩溃会停止 Claim 并由 Lease 产生 LOST，但内存槽无法
跨进程保存；在开放自动并发恢复前，还需解决重启后外部 ShadowBot 仍运行时的状态核对。

同一设备三个影刀 Task A/B/C 的 V1 语义：

```text
A RUNNING；B/C PENDING
A SUCCESS 或 FAILED → 释放槽 → B RUNNING
B SUCCESS 或 FAILED → 释放槽 → C RUNNING
```

当前 Backend 使用 `created_at ASC, task_id ASC` 稳定 Claim。同一个 Task 失败不会阻塞后续 Queue。

## Scheduler 边界

Scheduler 不连接 Worker，也不调用 ShadowBot。时间到后只通过 Backend 创建普通 PENDING Task，
后续仍走 Poll → Claim → Lease → Executor。例如 09:00 同时生成 A/B/C 三个目标 PC-11 的影刀
Task，PC-11 capacity=1 时按稳定 Claim 顺序依次运行，Scheduler 不等待每个应用结束。

Scheduler V1 的 DAILY、IANA Timezone、COALESCE ONE 和数据库触发幂等全部属于 Backend；
Worker 0.4.7 不读取 Schedule、不保存 Cron、也不知道 Task 来源。它仍只认识普通 Task Contract。
