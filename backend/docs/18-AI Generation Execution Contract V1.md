# AI Generation Execution Contract V1

> - 状态：`FROZEN`
> - 审计日期：2026-09-03
> - 基线：Green `origin/dev` `cf88d4c675a4e278d4f5ebe2745f8ef840ac7ac2`
> - 范围：AI Workbench 图片生成的 Job、Item、输入、输出、状态、历史及服务器执行边界
> - Readiness：`READY FOR MIGRATION SLOT = YES`

## 1. Scope

本文只定义 AI Generation Execution V1 的最小业务契约。当前证据来自：

- 已实现的 AI Workbench Backend Foundation V1；
- 已实现的 Access、Module Access、Asset Scope 与 Asset Storage；
- 已冻结的 Frontend AI Generation Workspace / Generation Records V1；
- 当前真实 Model、Repository、Service、DTO、API 与 Tests。

本文不把 Development-only Fixture、浏览器 Object URL、模拟状态或临时 ID 变成 Backend Contract。
本文不实现 Production Code、Migration、Provider、Queue、Polling、Webhook、Frontend Real API 或真实生图。

## 2. Existing Foundation

Generation Execution 必须复用以下既有事实：

- `GenerationMode`：`NORMAL_GENERATION / STYLE_REPLICATION`。
- Frontend 工作方式：`INSTANT / BATCH`。
- `OutputRole`：`MAIN_IMAGE / DETAIL_IMAGE`。
- `OutputFormat`：`SINGLE / COLLAGE_2X2`。
- `GenerationSize`：当前管理契约中的 `1:1 / 3:4 / 4:3 / 16:9`。
- `TemplateGroup / PromptTemplate / ProductMaterialGroup / MaterialGroupAsset /
MaterialGroupTemplateBinding`。
- `HumanPrincipal → ActorContext → DataScopePolicy`。
- Membership 级 `ai-workbench` Module Access。
- `AssetService`、`AssetOwnership`、`AssetSourceType.AI_GENERATED` 与统一 Storage。

`PromptTemplate.count` 当前为 `1–8`，且只有一个 `prompt`。Generation Execution 不增加
`negative_prompt`，也不创建第二套 Mode、Role、Format、Size、User、Team、Scope 或文件系统。
当前 Frontend `GenerationConfig` 只有 `prompt / outputFormat / size / count`；没有已冻结的模型、Provider、
清晰度或质量参数，因此这些参数不进入提交或持久化 Schema。

V1 不建设 Prompt 变量系统。`PromptTemplate.prompt` 始终是完整 Literal Text；既有
`PromptTemplate.variables` 管理字段不参与 Generation Execution，不进入生成请求或执行 Snapshot，Prompt 中的
花括号和类似占位符的文本也不解析、不替换、不转义。

V1 不建设 Model Registry。Frontend/API 不选择或提交 Provider/Model；服务端运行配置根据当前图片生成业务
Capability 解析实际 Provider/Model。GenerationJob/Item 不持久化 `provider_id / provider_name / model_id`
或 Provider Payload。

## 3. Job / Item 模型语义

### 3.1 GenerationJob

`GenerationJob` 表示用户点击一次“生成”或“开始生成”后，被 Backend 接受的一次整体提交。它负责：

- `INSTANT / BATCH` 工作方式；
- `NORMAL_GENERATION / STYLE_REPLICATION` 业务模式；
- `team_id / created_by_user_id` Ownership；
- 创建、开始、完成时间与整体状态；
- 本次提交的稳定幂等标识与规范化请求指纹；
- 从全部 Item 派生的总数、成功数、运行数、等待数与失败数；
- 作为生成记录的 Source of Truth。

Job/Item 不保存 Provider/Model 标识、Provider 原始 Payload、Storage Key、浏览器预览 URL 或通用
Task/Worker 字段。

### 3.2 GenerationItem

`GenerationItem` 是可独立成功或失败的最小生成单位：一个 Item 最多产生一个正式图片 Asset。

- 即时生成：`count = N` 展开为 N 个稳定 Item，全部 Item 共享提交时选定的输入集合和有效配置。
- 批量生成：按 Product Material Group → Template Group → Prompt Template → 输出序号展开 Item。
- 风格复刻批量生成：当前前端计划为每个有效 Style Reference 分别执行模板数量，因此 Item 粒度为
  `Product × PromptTemplate × StyleReference × ordinal`。
- `COLLAGE_2X2` 表示一个 Item 生成一张四宫格图片 Asset，不拆成四个 Item。

Product、Template Group 与 Template 层级是 Item Snapshot 的查询投影，不增加 Step、Workflow、
Execution Graph 或通用 Job Engine。

### 3.3 为什么需要两层

Job 承担一次提交、Ownership、列表与整体进度；Item 承担独立输出、状态、失败和重试。只用 Job 无法表达
“3 张成功、1 张失败”并保留成功 Asset；只用 Item 则无法稳定表达一次批量提交和生成记录。

## 4. Submit Contract

### 4.1 通用提交规则

Human Submit API 必须先解析 `ActorContext` 并校验 `ai-workbench` Module Access。公开 DTO 不接受
`team_id`、`created_by_user_id`、`data_scope`、Provider/Model、Provider Credential 或 Storage 字段。

提交采用异步业务语义：Backend 完成同步校验、计划展开和 Snapshot 后创建 Job/Items，立即返回 Job；
HTTP 不等待 Provider 完成全部图片。

创建请求必须带客户端生成的稳定 `submission_key`。Job 同时保存 `submission_fingerprint`，它是排除
`submission_key` 后，对规范化用户提交 DTO 计算的稳定摘要；有序 ID、枚举与最终用户输入均参与摘要，
服务端随后解析出的 Product、Binding、Template 或 Item 计划不参与摘要。唯一性范围为当前
`team_id + created_by_user_id + submission_key`：相同 Key 与相同 Fingerprint 返回原 Job，不重新解析
数据库现状；相同 Key 与不同 Fingerprint 返回 Conflict。HTTP `request_id` 仅用于链路关联，不等价于
幂等键。该规则只解决昂贵生成提交的重复点击和网络重试，不保存完整原始请求，也不建设通用分布式
Idempotency Framework。

### 4.2 即时生成

当前可确定的提交语义为：

- `work_mode = INSTANT`；
- `mode`；
- 有序 `product_asset_ids`；
- 风格复刻时有序 `reference_asset_ids`；
- 可空的 Prompt Template 来源标识；
- 用户最终可编辑的 `prompt / output_format / size / count`。

本地文件必须先通过正式 Asset Upload 成为 Asset，再以 `asset_id` 提交；不能把 `File`、Object URL、
Base64 或本地路径放进 Generation 请求。

即时请求的 `prompt` 就是完整 `final_prompt`。选择 PromptTemplate 只允许 Frontend 将其 Literal Text 填入可编辑
输入，不允许 Backend 再拼接模板 Prompt 与请求 Prompt，也不解析任何变量。

即时生成固定 `output_role = MAIN_IMAGE`；Frontend/API 不增加或提交 Role 选择字段。即使请求带有
PromptTemplate 来源标识，也不继承该模板的 Role。

### 4.3 批量生成

当前可确定的用户选择语义为：

- `work_mode = BATCH`；
- `mode`；
- 产品范围：全部已启用或显式选择的 Product Material Group IDs；
- 模板来源：产品已配置 Binding 或本次显式选择的 Template Group IDs；
- 输出范围：`ALL / MAIN_IMAGE / DETAIL_IMAGE`。

“产品已配置”在提交时解析现有 Binding；“本次显式选择”只属于该 Job，不创建、替换或删除正式
`MaterialGroupTemplateBinding`。

批量 Item 的 `final_prompt` 直接等于对应 `PromptTemplate.prompt` 的 Literal Text；不拼接额外 Prompt，
不读取或解析 `PromptTemplate.variables`。批量 Item 的 `output_role` 继承对应 PromptTemplate 的
`MAIN_IMAGE / DETAIL_IMAGE`。

Backend 必须以提交时数据库事实重新执行计划校验，不能信任 Frontend Preflight 的数量、Enabled、Binding、
Asset Role 或 Item 列表。Frontend Preflight Skip 与 Runtime Item Failure 是不同语义：被跳过的 Product
不创建 Item，不进入运行失败数；至少存在一个可执行 Item 才创建 Job。Create 响应可以返回本次同步解析的
Skip 摘要供当前界面展示，但该摘要不是 Provider 失败，也不替代 Job/Item 历史。

## 5. Input Snapshot 语义

Job 被接受后必须使用提交时的稳定执行事实。之后修改或停用 PromptTemplate、TemplateGroup、
ProductMaterialGroup Binding、MaterialGroupAsset Role 或生成模式开关，不改变已提交 Item。

### 5.1 仅保存正式引用

- 输入图片保存为 Item 与 Asset 的有序关系；Asset 仍是文件事实唯一来源。
- Item 成功后只以 `output_asset_id` 关联正式 Asset。
- PromptTemplate、TemplateGroup 与 ProductMaterialGroup 的 ID 只作为可空来源追踪，不允许执行时重新读取
  最新配置。

来源实体删除后，历史仍由 Snapshot 保持可读。PromptTemplate、TemplateGroup 与 ProductMaterialGroup 的
Provenance FK 均为 nullable、`ON DELETE SET NULL`，不得通过 Cascade 删除 Job/Item。其中批量 Item 的
`source_product_material_group_id` 只表达来源，不是 Job 终态后的业务依赖。

### 5.2 必须冻结为 Snapshot

- Job 的 `work_mode`、`mode`、Creator 显示名与创建时间；
- Item 的稳定序号；
- 输入 Asset 的 Slot/Role 与顺序；
- 完整 Literal `final_prompt`：即时取请求 `prompt`，批量取对应 `PromptTemplate.prompt`；
- `output_role / output_format / size`；
- 来源 Product、Template Group、Prompt Template 的历史展示名；
- 批量 Item 的 Product/Group/Template 层级键；
- 提交时用于展开 Item 的有效配置。

`count` 不在每个 Item 重复保存；它在提交时展开为 Item 数量，Job 的 `total_count` 由 Item 数量得出。

### 5.3 不持久化

- Fixture ID、`visualMock=1`、模拟延时与模拟状态；
- `previewUrl`、Object URL、data URL、浏览器 File 或本地路径；
- 当前 Tab、筛选、分页、折叠、选中 Card、Dialog 状态；
- Frontend 派生文案和百分比；
- Provider 临时下载 URL、认证 Header、Secret、Stack Trace 或完整原始 Payload；
- Provider/Model 标识、Prompt 变量名及变量值；
- Preflight 控件的临时 Draft 和重复的模板/Asset JSON。

## 6. Asset 输入

所有输入图片继续基于 Asset Foundation：

1. Submit Service 对去重后的全部 ID 调用正式 Asset Scoped Lookup。
2. 返回集合必须与请求 ID 完整匹配。
3. 每个 Asset 必须为当前支持的 Image，并额外满足 `asset.team_id = job.team_id`。
4. `ALL` 即使能读取其他 Team Asset，也不能把它关联到当前 Team Job。
5. 不存在、不可读、错误 Team 或错误媒体类型均 Fail Closed；不得先建 Job 后补校验。

Item 与输入 Asset 的关系至少表达 `item_id / asset_id / input_role / position`。普通生图 Item 关联提交时的
Product Source 集合；风格复刻 Item 同时关联 Product Source，并按当前粒度关联对应 Style Reference。
不得用 `storage_key` 副本、通用 JSON ID 数组或新的 `generation_files` 表代替正式关系。

被 Job/Item 引用的输入 Asset 仍是历史和失败项重试所需事实，Asset 删除必须复用 `ASSET_IN_USE` 保护，
不能 Cascade 清除执行关系。

## 7. Asset 输出

Provider Adapter 成功只返回待归档的安全文件流/字节流及必要媒体元数据。Generation Service 使用：

```text
AssetOwnership(
  team_id=job.team_id,
  created_by_user_id=job.created_by_user_id,
)
```

调用 `AssetService.create(..., media_type=IMAGE, source_type=AI_GENERATED)`。Provider 无权决定 Asset
Ownership、Asset ID 或 Storage Key。

一个 Item 只有在输出已进入 Asset Foundation、`output_asset_id` 已建立且必要的业务归档完成后，才可成为
`SUCCESS`。Provider URL 只允许作为 Adapter 内短生命周期执行信息，绝不永久保存为结果。

`AI_GENERATED` 是 Asset 来源；`AI_OUTPUT` 是 Asset 与 ProductMaterialGroup 的关系角色，二者不能混用：

- 即时生成：成功即创建正式 Asset，但默认不建立 ProductMaterialGroup 关系；用户“保存到素材库”时，
  通过可信 AI Workbench Service 将现有输出 Asset 以 `AI_OUTPUT` 关联到同 Team 目标组。
- 批量生成：成功结果自动以 `AI_OUTPUT` 关联提交时对应的同 Team ProductMaterialGroup。

`output_asset_id` 是 Item 对正式 Asset 的引用。输入或输出 Asset 只要仍被 GenerationJob/Item 引用，
Asset 删除就必须复用 `ASSET_IN_USE` 保护；不得删除 Asset 后让历史结果降级为失效 Provider URL，也不得
通过 Cascade 清空执行关系。

Item 同时保存最小归档历史：nullable、`ON DELETE SET NULL` 的 `archived_material_group_id`、
`archived_material_group_name_snapshot` 与 `archived_at`。这些字段表达结果曾被归档的历史事实；当前是否仍有
`MaterialGroupAsset` 关系由关系表表达。批量成功时归档目标固定为该 Item 的来源 ProductMaterialGroup；
即时结果只允许首次显式保存选择一个同 Team 目标组，重复同一保存请求幂等返回，已归档后改投其他组返回
Conflict。目标组后续删除或关系后续 detach 不篡改归档历史。

输出落库必须复用 Asset Foundation 的校验、Storage 与 Ownership 规则，并提供一个受控的事务编排边界：

1. 即时 Item 的 Asset Row 与 `output_asset_id` 在同一数据库事务提交后，Item 才成为 `SUCCESS`；
2. 批量 Item 的 Asset Row、`output_asset_id`、`AI_OUTPUT` 关系和归档历史在同一数据库事务提交后，Item
   才成为 `SUCCESS`；
3. 即时结果显式保存时，`AI_OUTPUT` 关系与 Item 的归档历史在同一数据库事务提交；任一写入失败则整体
   回滚，Item 保持 `SUCCESS` 且未归档；
4. Storage 写入或数据库事务失败时，复用 Asset Foundation 的 Rollback 与 Storage 补偿规则，不保留已提交但
   未关联 Item 的孤儿 Asset；
5. 同一 Item 的重复完成/回调在行锁下复用已有 `output_asset_id`，不得创建第二个输出 Asset。

当前 `AssetService.create()` 自己提交事务。正式实现必须在 Asset 模块内提供或复用事务感知的内部能力，
不能在 Generation Feature 复制第二套 Asset 创建逻辑。该要求属于后续实现边界，本轮不修改代码。

ProductMaterialGroup 删除必须扩展既有聚合删除 Service Guard：

- 只要存在通过 Item `source_product_material_group_id` 引用该组，且状态为 `PENDING / RUNNING` 的
  GenerationJob，拒绝删除；
- 相关 Job 全部为 `SUCCESS / PARTIAL_FAILED / FAILED` 后，允许按既有 ProductMaterialGroup 聚合删除语义
  删除；
- 删除后 Provenance/归档 FK 由 `ON DELETE SET NULL` 清空，提交 Snapshot 保持不变；
- 删除 ProductMaterialGroup 不得删除 GenerationJob、GenerationItem、输出 Asset，也不得修改 Frozen
  Snapshot；其 `MaterialGroupAsset` 关系仍按既有聚合删除语义处理。

数据库 `ON DELETE SET NULL` 只保护终态历史完整性，不能替代 Service 对非终态 Job 的显式引用检查。

## 8. Status Machine

### 8.1 Job Status

V1 最小状态固定为：

- `PENDING`：Job/Items 已创建，尚无 Item 开始执行。
- `RUNNING`：至少一个 Item 正在执行或等待继续，且尚未全部终结。
- `SUCCESS`：全部 Item 成功。
- `PARTIAL_FAILED`：全部 Item 已终结，至少一个成功且至少一个失败。
- `FAILED`：全部 Item 失败。

Frontend 的 `QUEUED` 与 `WAITING` 均映射 Backend `PENDING`，不创建第二套等价持久化状态。

### 8.2 Item Status

V1 最小状态固定为：

- `PENDING`
- `RUNNING`
- `SUCCESS`
- `FAILED`

不增加 `CLAIMED / LEASED / HEARTBEAT / LOST / ORPHANED`。这些属于现有 Device Worker Task 执行面，
不是服务器 AI Generation 的当前业务事实。

### 8.3 派生规则

Job 状态和统计只能由 Item 状态派生，客户端不能写入：

- 全部 PENDING → Job PENDING；
- 存在 PENDING/RUNNING，且并非全部 PENDING → Job RUNNING；
- 全部终态且全成功 → SUCCESS；
- 全部终态且全失败 → FAILED；
- 全部终态且成功、失败并存 → PARTIAL_FAILED。

例如 3 个 Item 成功、1 个失败时，Job 为 `PARTIAL_FAILED`。

## 9. Partial Failure

单个 Item 失败不能回滚、删除或降级其他已成功 Item 和 Asset。Job 的 `PARTIAL_FAILED` 是正常可查询终态，
不表示数据库事务整体回滚。成功结果继续可预览、下载、保存或按批量规则归档。

Frontend Preflight Skip 不创建 Item，因此不参与 Job 的成功、失败或完成百分比。

## 10. Retry

V1 支持“只重试失败 Item”，不提供“重跑整个 Job”的独立语义。即时结果按钮、批量 Template 层按钮和
生成记录“重试失败项”只是选择一个或多个 FAILED Item 的不同 UI 入口，Backend 接收稳定 Item ID 集合。

V1 不增加 Attempt 表，也不创建新 Job/Item。`attempt_count` 初始为 1；重试 DTO 对每个 Item 提交
`item_id + expected_attempt_count`。Service 在一个事务内锁定本次全部 Item，并按预期次数执行
Compare-and-Set：

1. 当前为 `FAILED` 且 `attempt_count = expected_attempt_count` 时，原 Item 转为 `PENDING` 并将次数加 1；
2. 当前次数大于 Expected 时，视为该请求已经被接受，返回 Item 当前状态，不再次启动；
3. 当前次数等于 Expected 但状态不是 `FAILED`，或当前次数小于 Expected 时返回 Conflict；
4. 原成功 Item 与 Asset 不变；
5. 保留 `last_failure_code / last_failure_message / last_failed_at`，重试开始时不得清空；
6. 新尝试成功后，当前状态、`output_asset_id` 和完成时间表达最终结果，上一失败摘要与尝试次数仍可审计；
7. 新尝试再次失败时更新“最近一次失败”字段，不承诺保存每一次 Provider Attempt 的完整事件历史。

该最小语义满足当前 UI 对最终结果、失败原因和重试次数的需求；当前没有逐 Attempt 时间线需求，因此不引入
Attempt/Event Sourcing。Expected Count 与行锁为 Retry 提供持久幂等与并发保护，不新增 Retry Request 表或
通用幂等框架。

唯一例外是 Provider Create 已经开始、但 External Task ID 未能确认并持久化的
`PROVIDER_CREATE_OUTCOME_UNKNOWN`。该状态无法证明外部任务未创建，标准 Failed Item Retry 必须返回 HTTP
409 且不得增加 `attempt_count`，避免重复生成或重复计费；后续只有在 Provider 提供可验证的幂等恢复能力或新增
明确的人工处置契约后才能开放。Create POST 后的超时、连接中断、无效响应或缺少 Task ID 均属于该状态；
Provider 明确拒绝创建不属于该状态。

批量 FAILED Item 重试前还必须确认 `source_product_material_group_id` 非空，且来源组仍存在于当前 Team；
否则复用 `PRODUCT_MATERIAL_GROUP_NOT_FOUND` 拒绝本次重试并保持 Item 不变。Frozen Snapshot 不用于重建已
删除的商品组。该限制只影响删除来源组后的新重试，不改变删除前已完成 Item、输出 Asset 或历史记录。

## 11. Cancel

V1 不支持取消。当前 Frontend 没有生成任务取消入口，也没有 Provider 取消能力的正式证据，因此状态机不含
`CANCELLED / CANCELLING`，API 不提供 Cancel。Dialog 的“取消”只关闭表单或保存弹层，不是取消 Job。

## 12. Provider Boundary

Generation Execution Service 面向未来 Adapter 提供每个 Item 的标准业务输入：

- 稳定 Item ID；
- `GenerationMode`；
- 完整 Literal `final_prompt`；
- `OutputRole / OutputFormat / GenerationSize`；
- 经 Asset Service/Storage 安全读取的输入图片内容与顺序。

Adapter 标准返回只有两类：

- 成功：一个受支持的图片文件流/字节流、文件名建议与真实 Content Type；
- 失败：稳定分类、可安全展示的消息，以及仅供执行策略使用的可重试判断。

Provider/Model 由服务端当前运行配置根据图片生成业务 Capability 决定，不是 Human Submit 输入，也不是
GenerationJob/Item 历史字段。Provider 名称、模型 ID、请求字段、任务 ID、临时 URL、Webhook Payload 和原始
错误均不得进入 Generation Execution 业务 Schema；Provider Credential 只能来自 Backend 安全配置。

未来真实 Provider 如果需要 External Task Reference 才能异步恢复，由独立 Provider Adapter Feature 根据其
真实能力最小增加在 Adapter Execution 边界，不提前加入本 Contract 的 GenerationJob/Item Schema，也不得
伪装成用户可写字段。

## 13. Async / Progress

Frontend ↔ Backend 采用：

```text
Create Job
↓
立即返回 Job ID 与初始状态
↓
Frontend 查询 Job Detail / Record List
↓
Backend 返回 Item 状态和派生统计
```

V1 的 Frontend Progress Contract 为短轮询 Job Detail；轮询间隔、退避和页面缓存属于 Frontend 实现，
不进入数据库 Schema。当前阶段不冻结 WebSocket/SSE。

Backend ↔ Provider 的同步调用、Provider Polling 或 Webhook 由后续 Adapter 根据真实 Provider 能力决定，
不是业务 Schema 字段。异步业务契约不等于选定 Celery、Redis、RabbitMQ、Kafka 或任意 Queue 技术。

## 14. Generation Record

`GenerationJob` 就是生成记录的 Source of Truth，不创建 `GenerationHistory` 第二张历史表。

列表最小投影：

- Job ID、工作方式、Mode、整体状态；
- `created_at / created_by`；
- 总数、成功数、失败数与必要输入摘要。

详情最小投影：

- Job 列表字段及开始/完成时间；
- 即时生成的 Input Slot 名称、输入 Asset 摘要、模板来源与最终有效配置；
- 批量生成的 Product → Template Group → Prompt Template → Item 层级 Snapshot；
- 每个 Item 的稳定 ID、序号、Role、Size、状态、输出 Asset、归档状态和安全失败摘要。

归档状态来自 Item 的 `archived_at` 与归档目标 Snapshot，不从当前 `MaterialGroupAsset` 关系反向推导历史。

创建人名称、Product/Group/Template 名称均使用提交时 Snapshot，避免后续改名改变历史。百分比、状态文案与
`resultSummary` 由正式字段派生，不作为客户端可写事实。Provider 原始 Payload 不属于生成记录。

## 15. Ownership / Scope

Job 创建时固定：

```text
team_id = actor.team_id
created_by_user_id = actor.user_id
```

公开 DTO 不接受覆盖。Repository 列表、详情使用 `DataScopePolicy`：

- `SELF`：当前 Team 且当前 User 创建；
- `TEAM`：当前 Team；
- `ALL`：只扩大读取。

Retry、即时结果保存及其他写操作仍必须在当前 Active Team 的写边界内解析 Job、Item、Asset 与目标
ProductMaterialGroup。`ALL` 不允许修改其他 Team Job，不允许提交跨 Team 输入，也不允许把输出写入其他
Team。异步执行从持久 Job Ownership 创建 Asset，不信任 Provider，也不重新构造伪造 ActorContext。

## 16. Module Access

全部 Human Generation API 继续属于 `ai-workbench`，必须使用 Human Auth、ActorContext 与现有
`ModuleCode.AI_WORKBENCH` Guard。不新增 `ai-generation` Module/Permission。

服务器内部执行入口不是 Human HTTP API，不重复解析 Membership；它只能消费已经通过正式 Submit Service
创建的 Job。

## 17. Error / Failure

### 17.1 同步 API 错误

- Human Auth、Team Context、Module Access：复用现有统一错误。
- 输入 Asset 不存在、不可读、错误 Team：复用 `ASSET_NOT_FOUND / 404`。
- ProductMaterialGroup、TemplateGroup、PromptTemplate 来源无效：优先复用 AI Workbench 现有 Not Found
  与 Binding 校验语义。
- 字段、重复 ID、Mode/Role/Enabled/输入组合或无可执行 Item：使用统一 Validation/Error Envelope。
- 幂等 Key 与不同规范化请求冲突：HTTP 409。
- Job/Item 不存在或不在可读/可写 Scope：统一资源 Not Found，不泄漏跨 Team 存在性。
- 非 FAILED Item 重试或并发重试：HTTP 409。
- ProductMaterialGroup 存在 `PENDING / RUNNING` GenerationJob 引用：
  `PRODUCT_MATERIAL_GROUP_HAS_ACTIVE_GENERATION_JOBS / 409`，拒绝删除且不修改任何业务事实。

错误命名复用现有 `DeviceHasActiveTasksError` 的“资源 + 活跃任务”领域模式，以及统一 `AppError / ErrorResponse`
Envelope；不复用 `DEVICE_HAS_ACTIVE_TASKS`，也不建立通用 Conflict Framework。其他 Generation 专属 Code
在实现其具体 API 时按一个场景一个稳定语义审查，不得建立多套异常体系。

### 17.2 异步执行失败

Provider、输出校验、Storage 或归档失败发生在 Job 已返回之后，必须落为 `GenerationItem.FAILED`，不能在
后续查询中伪装成 HTTP 500。最小安全信息为：

- `last_failure_code`：稳定、非 Provider 私有的分类；
- `last_failure_message`：可安全展示的摘要；
- `last_failed_at`。

Provider Execution 已存在但当前 Attempt 的 External Task ID 为空时，以
`PROVIDER_CREATE_OUTCOME_UNKNOWN` 记录安全失败摘要；恢复与标准 Retry 均不得再次调用 Provider Create。

完整 Stack Trace、认证 Header、Secret、Provider 原始请求/响应和敏感图片 Payload 只允许进入受控内部日志，
不进入公开 DTO 或业务表。本文不建设新的 Logging/Audit 系统。

## 18. Task / Worker Boundary

AI Generation 是 Backend 服务器执行面，不依赖 Windows Worker、Device、Worker Token、Skill Registry、
Claim、Lease 或 Task Event。

现有 `Task` 强制包含 `target_device_id / skill_id`，状态为
`PENDING / RUNNING / SUCCESS / FAILED / LOST`，由 Device Worker Claim 和 Lease 驱动；它不具备当前 AI
Job 的 Team Ownership、Item 部分成功或输出 Asset 归档语义。因此 V1 不复用 Task，也不把 AI 请求伪装为
Device Skill。两类执行面只共享正式 Access、Asset、HTTP、错误与分层基础设施。

## 19. Explicitly Not Implemented

本轮只冻结 Contract，明确不实现：

- SQLAlchemy `GenerationJob / GenerationItem` Model；
- Alembic Migration、Migration Slot、Feature DB 或任何数据库写入；
- Repository、Service、DTO、API Production Code；
- Provider Adapter、Provider Credential、Model Registry 或真实模型调用；
- Queue、Scheduler、Celery、Redis、RabbitMQ、Kafka、Webhook、SSE 或 WebSocket；
- Windows Worker / Device Task 集成；
- Cancel、整 Job Retry、Attempt、Step、Workflow、Event Sourcing 或 Generic Job Engine；
- Provider 原始 Payload/URL 的持久化；
- Frontend Real API、Visual Mock 删除或 Frozen Assets/Templates 修改；
- 视频、音频、局部重绘、扩图、无限画布、计费、额度或成本系统。

## 20. Resolved Schema Decisions

### D1. Model / Provider

- V1 不建设 Model Registry。
- Frontend/API 不选择或提交 Provider/Model。
- GenerationJob/Item 不保存 Provider/Model 标识或 Payload。
- 服务端运行配置按图片生成业务 Capability 决定实际 Provider/Model。
- 未来 External Task Reference 只在有真实异步 Provider 证据时进入独立 Adapter Execution 边界。

### D2. Prompt Literal Text

- V1 不支持 Prompt 变量、缺值解析、替换、转义或 Template Engine。
- 即时请求 `prompt` 是完整 `final_prompt`。
- 批量 Item 的 `final_prompt` 直接等于对应 `PromptTemplate.prompt`。
- 不自动拼接模板 Prompt、请求 Prompt 或第二份 Prompt。

### D3. Output Role

- 即时生成固定 `MAIN_IMAGE`，不增加 Role 选择或请求字段。
- 批量生成继承 PromptTemplate 的 `MAIN_IMAGE / DETAIL_IMAGE`。

### D4. ProductMaterialGroup Delete

- 存在引用该组的 `PENDING / RUNNING` GenerationJob 时，以
  `PRODUCT_MATERIAL_GROUP_HAS_ACTIVE_GENERATION_JOBS / 409` 拒绝删除。
- 相关 Job 全部终态后允许删除。
- `source_product_material_group_id` 是 nullable、`ON DELETE SET NULL` 的 Provenance FK。
- 删除不影响 GenerationJob、GenerationItem、输出 Asset 或 Frozen Snapshot。

### Remaining Blocking Questions

`NONE`。当前 Job/Item、输入关系、输出 Asset、状态、重试、归档、Ownership 与 Provenance 语义足以进入
Generation Execution 的下一次 Migration Schema Review；具体 SQL 类型、约束名和索引仍须在取得正式 Slot 后
遵循当时最新 Green `dev` 与 Migration 规范确定，不构成业务 Contract 阻塞。

- 本文状态：`FROZEN`。
- `READY FOR MIGRATION SLOT = YES`。
