# worker/AGENTS.md

## 1. 定位
Worker 是运行在执行电脑上的常驻执行代理。

负责：
- 注册设备
- Heartbeat
- Claim Task
- Lease
- 启动执行器
- 汇报进度
- 收集日志
- 回传结果
- 回传附件

Worker 不是 UI、业务数据库、店铺全局配置中心或 AI 决策系统。

## 2. 文档路由
先读 `worker/docs/00-文档索引.md`。

| 任务 | 必读 |
|---|---|
| Worker 核心 | 01 + 02 |
| Task Claim/Lease | 02 |
| 新增 Skill 执行器 | 03 |
| 接影刀 RPA | 03 + 04 |
| 日志/错误/结果 | 05 |
| 测试 | 06 |

## 3. RPA 不直接管理服务器
RPA 不负责：
- 轮询服务器
- 数据库连接
- 获取任意店铺凭证
- 全局任务状态
- 权限判断

统一：
```text
Backend
↓
Worker
↓
Executor
↓
RPA / Script
```

## 4. Executor 抽象
必须通过统一 Executor 抽象：
- RPAExecutor
- PythonExecutor
- NodeExecutor
- BrowserExecutor
- ExeExecutor

禁止 Task Dispatcher 中写大量不同启动细节。

## 5. Skill Contract
每个 Skill 必须有稳定：
- skill_id
- input
- output
- error
- timeout
- runtime

不得每个 Skill 自创通信格式。

## 6. 凭证
Worker 只能按 Task 获取必要 Credential/Session。
禁止本地永久同步服务器全部账号密码。
日志禁止输出密码、完整 Cookie、Token。

## 7. 第三方库与抽象
- HTTP 使用统一 Client。
- 系统信息使用统一 Device/System Service。
- 进程启动使用统一 Process/Executor 抽象。
- 重试使用统一策略。
- 不允许每个 Skill 各写一套日志、超时和 subprocess 管理。

## 8. Worker 与 Electron
Worker 独立运行。
Electron 只管理其进程生命周期。
Electron 关闭不能成为 Worker Task 可靠性设计的前提。

## 9. Business Skill 开发硬约束
- 新增 Worker 业务能力必须以稳定 `skill_id` 注册为 `business` Skill。
- Python Business Skill 必须使用 `app/skills/sdk/` 内部 SDK 和结构化 Pydantic Input。
- Business Skill Input Model 是输入 Contract 的唯一 Source of Truth；允许由它生成对外 Schema，禁止为 Frontend、Scheduler 维护第二份手写参数定义。
- Business Skill 不得实现 Heartbeat、Poll、Claim、Lease、Task 状态或 Backend Event HTTP。
- Business Skill 不得直连 PostgreSQL，也不得自行读取 Worker Token 或配置文件。
- 日志和进度只通过 `SkillContext.log()` / `SkillContext.progress()` 上报。
- 成功必须返回 `SkillResult`；预期失败必须抛出 `SkillExecutionError`。
- Executor / Provider 并发由 Worker Runtime 控制，禁止 Skill 内部轮询等待执行槽。
- 详细契约与示例见 `docs/03-Skill执行规范.md` 和 `examples/demo_progress_skill.py`。

## 10. 本地输入桥接硬约束
- 影刀等外部程序需要固定本地输入时，必须复用 Worker Local Input Bridge，不得由每个 Application 自创路径或写入协议。
- 普通业务参数、账号 Payload 和图片分别使用配置的 `params.json`、`account.json` 与固定图片工作目录。
- Python Business Skill 不得为了与外部程序“统一”而读取 `params.json`；业务参数继续使用 Pydantic Input。
- Python Business Skill 的账号和图片路径只通过 `ctx.accounts` 与 `ctx.paths.images` 获取。
- 完整账号 Payload 不得写入日志、Runtime Event 或 Task Result。
- 没有真实上游契约时，不得提前引入 Resource Manager、Secret Resolver、Task Workspace 或图片传输协议。

## 11. 多店铺任务上下文（硬规则）

- 一个 Task 可以携带多个有序 Shop Account Context；Worker Core 不得按 Shop 拆 Task 或创建子 Task。
- 同一个 Shop 可以被多台 Device 同时执行，不建立 Shop 全局锁；当前 Worker 仍保持单 Active Task。
- 多 Shop 的串行、并发、切号与单店失败策略由 Yingdao Application 或 Business Skill 决定。
- Backend、Worker 内部模型和 `ctx.accounts` 均使用英文 Account 字段。
- 仅 Local Input Bridge 写 `account.json` 时映射中文字段，根对象固定为 `店铺列表`；无账号时也写空列表。
- 当前 Account Payload 不包含验证码或登录挑战流程。
