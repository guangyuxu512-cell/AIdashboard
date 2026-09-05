# AI Provider V1

> - 状态：`IMPLEMENTED`
> - 日期：2026-09-05
> - Provider：ToAPIs
> - Model：`gpt-image-2`
> - Migration：`20260905_0030_ai_provider_v1`

## 1. Scope

AI Provider V1 为既有 GenerationJob / GenerationItem 接入第一家真实图片生成 Provider。它只实现：

```text
PENDING Item
→ RUNNING
→ 持久化 Provider Execution Intent
→ 上传输入 Asset
→ 创建 ToAPIs Task
→ 持久化 External Task ID
→ 轮询并下载图片
→ AssetService
→ SUCCESS / FAILED
```

本实现复用 Generation Execution V1 的 Job、Item、输入关系、Retry、状态派生、Asset、Storage 与 Ownership。
Frontend、Human Submit DTO 与生成记录 DTO 不增加 Provider/Model 字段。

## 2. Provider Adapter

ToAPIs Adapter 是单一薄适配层：

- `POST /v1/uploads/images`，multipart 字段为 `file`，`purpose=generation`；
- `POST /v1/images/generations`，提交 `gpt-image-2`、Literal `final_prompt`、`size`、服务器配置的
  `resolution / quality`、`n=1`、`response_format=url` 与上传后的 `image_urls`；
- `GET /v1/images/generations/{task_id}`，轮询到成功或失败；
- 成功只读取 `result.data[].url`，下载后立即交给 Asset Foundation；
- 失败把 Provider `error.code` 映射为受控领域码和固定产品文案；原始 `error.message` 不落库、不记录日志、
  不返回 Frontend。

Bearer API Key、Base URL、Model、Resolution、Quality、Poll Interval 与 Timeout 只来自 Backend Settings。
API Key 不进入数据库、Frontend、业务错误或日志。

截至 2026-09-06，[ToAPIs 官方 `gpt-image-2` 创建接口文档](https://docs.toapis.com/docs/cn/api-reference/images/gpt-image-2/generation)
只定义 Bearer 鉴权、生成请求字段及响应 Task ID，没有明确承诺 `Idempotency-Key`、客户端唯一引用或按客户端
键恢复创建结果的能力。因此 V1 不发送未经官方确认的幂等 Header，采用本地 Durable Intent 与 Fail-Closed
恢复策略。

当前国内运行环境默认使用 `https://toapis.cn`；海外部署可通过环境配置切换至 `https://toapis.com`。Base URL
必须是无路径、无凭据的 HTTPS Origin。

`NORMAL_GENERATION / STYLE_REPLICATION` 共用同一接口，差异已经冻结在 Item 的输入 Asset 关系和完整 Prompt。
旧工具对 `COLLAGE_2X2` 的真实映射是不提交独立 Provider 字段、仍请求一张结果；当前 Adapter 同样保持
`n=1` 并原样提交 `final_prompt`，不追加或改写四宫格文案。`output_format` 继续作为 GenerationItem 业务
Snapshot，不反向推导 Prompt。

## 3. Provider Execution Persistence

`generation_provider_executions` 只保存当前有效外部执行：

| 字段                 | 语义                                     |
| -------------------- | ---------------------------------------- |
| `generation_item_id` | 主键；一个 Item 最多一个当前执行         |
| `provider_code`      | V1 固定 `toapis`                         |
| `external_task_id`   | 可空；ToAPIs 返回后立即写入的异步任务 ID |
| `attempt_count`      | 创建该外部任务时的 Item Attempt          |
| `created_at`         | 当前关系行首次创建时间                   |
| `updated_at`         | Retry 替换当前外部任务后的更新时间       |

调用 Provider 前，执行器先以当前 `generation_item_id / provider_code / attempt_count` 创建或更新同一行，令
`external_task_id = NULL`，并独立提交该事务。只有该 Durable Intent 已提交后才允许调用 ToAPIs Create；创建
成功后立即在同一行写入 External Task ID，再开始轮询。Retry 不创建 Attempt、History 或 Payload 表，而是为
新 Attempt 重置并复用同一行。

## 4. Recovery and Attempt Safety

Backend lifespan 启动一个当前进程内的顺序执行循环：

- 当前 Attempt 没有 Provider Execution 时，先提交空 Task ID Intent，再允许创建一次；
- `RUNNING` 且当前 Attempt 已有 External Task ID 时，直接恢复轮询原 Task，不重新上传或创建；
- 恢复时当前 Attempt 已有 Provider Execution、但 External Task ID 仍为空时，外部创建结果视为未知，禁止再次
  Create，并以 `PROVIDER_CREATE_OUTCOME_UNKNOWN` 使 Item Fail Closed；
- ToAPIs Create POST 已发出后发生超时、连接中断、无效响应或缺少 Task ID 时，同样视为未知结果；上传阶段失败
  或 Provider 明确拒绝创建仍使用原有普通失败语义；
- 上述未知结果不允许标准 Failed Item Retry，返回同码 HTTP 409，必须等待人工决定后续处理；
- 写入 Task ID、SUCCESS 或 FAILED 前都在行锁下核对 Item `attempt_count`；
- Provider Execution 的 Attempt 与 Item 当前 Attempt 不一致时，不复用旧 Task；
- 旧 Attempt 的迟到成功或失败结果只被忽略，不能覆盖新 Attempt。

V1 是单服务器、单 Backend 进程执行边界，不引入 Lease、Claim、Heartbeat、Celery、Redis、Kafka、Windows
Worker 或通用 Scheduler/Queue Framework。

## 5. Input and Output

Generation Service 在创建 Job 前、首次能确定单个 Item 实际输入数量的位置执行唯一的 16 张限制校验；超过
16 张返回既有 `GENERATION_PLAN_TOO_LARGE / 422`，不截断、不先创建 Item，也不在 Adapter 重复建设
Capability 校验。

输入顺序保持 Product Source 在前、Style Reference 在后。执行器只打开已由 Generation Service 固化并验证的
Asset Storage Key；Provider 不决定 Team、User、Scope 或 Asset Ownership。

结果 URL 必须是可信 ToAPIs HTTPS Host，只存在于 Adapter 的当前调用内。图片下载后通过
`AssetService.stage_for_transaction` 创建 `IMAGE / AI_GENERATED` Asset：

```text
team_id = GenerationJob.team_id
created_by_user_id = GenerationJob.created_by_user_id
```

Asset Row、Storage、Item `output_asset_id`、批量结果归档与 Item SUCCESS 继续使用 Generation Execution V1
已有事务边界。Provider URL 不持久化。

应用日志初始化将 `httpx / httpcore` 依赖日志限制为 `WARNING`，避免 INFO 请求日志记录带签名查询参数的
Provider 结果 URL。

## 6. Failure

Provider HTTP、响应、终态失败、超时与结果下载错误只落为安全的：

- `last_failure_code`；
- `last_failure_message`；
- `last_failed_at`。

业务表不保存 Authorization Header、API Key、完整 Provider Payload、Stack Trace 或带查询参数的结果 URL。
普通失败 Item 继续复用既有 Failed Item Retry；新 Attempt 重新走同一执行链。只有
`PROVIDER_CREATE_OUTCOME_UNKNOWN` 禁止标准 Retry，避免重复生成和重复计费。

## 7. Explicitly Not Implemented

- 多 Provider、Provider 表或管理 UI；
- Model Registry 或用户选择 Model；
- Provider Payload / History / Attempt 表；
- Queue 平台、分布式 Worker、Lease、Claim 或 Heartbeat；
- Frontend Real API 改造；
- AI 视频、取消或 Webhook。
