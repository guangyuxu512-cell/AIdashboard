# AI生图接入中控台 Access & Ownership Foundation V1 方案

> 中文正式名称：**访问控制与数据归属底座 V1**
> 英文正式名称：**Access & Ownership Foundation V1**
> 方案日期：2026-09-01
> 范围：只设计 AI 生图接入现有中控台底座的方案，不修改生产代码、不创建 Migration、不开始 Backend 实现。

## 1. 当前 AI 状态

根据《AI生图模块现状与后端接入需求 V1》：

- `/ai-workbench/generate` 是禁用控件与 Empty State 组成的 Prototype；没有提交、任务、结果、Store、Query 或 AI API Client。
- `/ai-workbench/assets`、`/ai-workbench/templates` 的交互只存在于 Development 环境且精确 `?visualMock=1` 的本地 Fixture / 内存状态；正式路由仍是禁用控件与 Empty State。
- AI 专属 Backend 目前没有 API、Service、Repository、Model、Migration、Provider Adapter、Queue 或历史查询。
- 通用 Assets、Human Auth 与 Access Foundation 已存在，但 AI Workbench 尚未调用它们。

本方案的目标是让未来 AI Backend 使用现有底座，而不是把当前 Visual Mock 或通用 Task 机械复制成另一套权限、文件或执行系统。

## 2. 当前中控台底座

### 2.1 人员身份认证：Human Auth V1

现有正式身份链路为：

```text
人员登录
↓
服务端 Human Session（HttpOnly Cookie）
↓
HumanPrincipal(user_id, display_name)
↓
ActorContext
```

- `get_human_principal` 从固定 Cookie 解析会话；不接收 `X-User-ID` 等可伪造身份 Header。
- `HumanPrincipal` 只含 `user_id` 与 `display_name`，不含 Team、Role、Scope 或 ORM 对象。
- `HumanSession` 是服务端会话记录，人员身份和 Worker Device Token 两套身份严格分离。

证据：`backend/app/modules/human_auth/`、`backend/app/modules/access/auth.py`、`backend/docs/14-Human Auth V1.md`。

### 2.2 团队与数据范围：Access Foundation V1

现有正式请求上下文为：

```text
HumanPrincipal
↓
TeamMembership(role_code, data_scope)
↓
ActorContext(user_id, user_display_name, team_id, membership_id, role_code, data_scope)
↓
DataScopePolicy
```

- Active Team 由 `X-Team-ID` 表达选择意图，Backend 重新验证 User、Membership 和 Team 的启用状态。
- 单 Team 人员可自动选择 Team；多 Team 人员必须选择有效 Team。
- `DataScopePolicy` 统一实施：SELF = 当前 Team + 当前 Creator；TEAM = 当前 Team；ALL = 不追加 Ownership 读取条件。未知 Scope Fail Closed。
- ALL 只影响读取过滤，绝不允许创建无 Team 的业务实体。

证据：`backend/app/modules/access/contracts.py`、`dependencies.py`、`policy.py`、`service.py`、`backend/docs/13-Access Foundation V1.md`。

### 2.3 素材归属：Asset Scope V1

Asset 已是 Team Scoped Entity：

```text
Asset
├─ team_id              数据归属 Team，非空
└─ created_by_user_id   创建者，可空（仅历史/系统素材可无可靠 Creator）
```

已有关键正式能力：

- `AssetService.upload(actor=...)` 从 `ActorContext` 写入 Asset Ownership；公开 HTTP 不接收 Team/User Ownership 字段。
- `AssetService.list_accessible_by_ids(actor, asset_ids)` 在 SQL 层应用 `DataScopePolicy`，用于可信业务 Service 的参考素材校验。
- `AssetService.create(..., media_type, source_type, ownership)` 是可信内部入口；可显式传入 `AssetOwnership`，但不应暴露为让前端提交归属的 API。
- `AssetSourceType` 已正式包含 `upload`、`ai_generated`、`imported`；AI 生成图片可直接复用 `ai_generated`，无需扩展 Source Type。
- Asset 内容由统一 Storage 管理，正式 Human Content API 不返回 `storage_key` 或公开 URL。

证据：`backend/app/modules/assets/`、`backend/docs/12-资产与存储架构.md`、`backend/docs/15-Asset Scope V1.md`。

## 3. 接入总架构

未来 Human AI API 应采用以下链路：

```text
人员登录
↓
Human Session
↓
HumanPrincipal
↓
当前团队（统一 X-Team-ID）
↓
ActorContext
↓
AI Image Service
├─ 以 Asset Scoped Lookup 校验参考素材
├─ 创建具有 Ownership 的 AI Image Job
├─ 调用 AI Provider Adapter
└─ 成功后调用 AssetService.create(..., AI_GENERATED, ownership=Job Ownership)
↓
统一 Asset 媒体资产体系
↓
AI Job 返回生成结果对应的 Asset 标识 / 可读取结果
```

边界要点：

1. AI API 只依赖 `get_actor_context` 取得身份上下文，再将业务交给 AI Image Service。
2. 前端绝不提交 `user_id`、`team_id`、Creator 或 Ownership；它们全部派生自 `ActorContext`。
3. Provider 调用只在 Provider Adapter 中；Provider Credential / Model Config 属于系统基础设施配置，不属于人员 Ownership。
4. 生成文件进入现有 Asset 体系；不建立 `ai_generated_files`、第二张图片表或第二套 Storage。

## 4. Ownership 设计

### 4.1 AI Image Job

AI Image Job 是“一次生成业务过程”，不是媒体文件。未来 Job 必须具有：

```text
team_id             = ActorContext.team_id
created_by_user_id  = ActorContext.user_id
```

语义如下：

- `team_id`：该 AI 生成任务属于哪个 Team，是 Team/SELF 查询的归属边界。
- `created_by_user_id`：谁发起了该次生成，用于 SELF 读取范围。
- 即使 `ActorContext.data_scope == ALL`，创建仍写入当前 Active Team；ALL 不能产生无 Team Job，也不允许由前端指定其他 Team。

AI Job 的历史读取应复用 `DataScopePolicy`，并按自身的 `team_id`、`created_by_user_id` 列应用：

| Scope | AI Job 可见范围 |
|---|---|
| SELF | 当前 Team 且当前 User 创建的 Job |
| TEAM | 当前 Team 的 Job |
| ALL | 不追加 Ownership 条件的 Job |

Repository 只接收已经解析的 `ActorContext` / Scope 结果；不得在 AI 模块写第二套 SELF/TEAM/ALL 判断。

### 4.2 Reference Asset

任何未来生成请求中的 `reference_asset_id`、`product_asset_id`、`template_asset_id` 或其他 Asset 引用，均必须在创建 Job **之前** 通过：

```text
AssetService.list_accessible_by_ids(actor, asset_ids)
```

或未来完全等价的正式 Scoped Lookup 校验。

校验要求：

1. 以请求中的引用集合进行 Scope SQL 查询；不能仅按 UUID 查询存在性。
2. 将返回记录与请求引用一一核对；数量缺失或标识不匹配即拒绝创建 Job。
3. Team A 人员猜测 Team B 的 Asset UUID 时，查询不能将其返回，AI Job 必须 Fail Closed，不得先创建后发现无权。
4. 不把前端 `previewUrl`、Object URL、data URL 或文件路径视为可信 Reference Asset。

Asset 是输入媒体事实；AI Job 只保存与其生成过程有关的引用关系或输入快照。两者不能合并为同一张表。

### 4.3 Generated Asset

Provider 成功生成图片后：

```text
AI Image Job Ownership
↓
AssetOwnership(team_id=job.team_id, created_by_user_id=job.created_by_user_id)
↓
AssetService.create(..., media_type=IMAGE, source_type=AI_GENERATED, ownership=...)
↓
生成 Asset
```

结果 Asset 继承 Job Ownership，使用现有 `AssetSourceType.AI_GENERATED`。AI Job 记录生成过程，Asset 记录最终媒体事实；两者保持分离，避免把 prompt、模型或 Job 状态塞进 Asset。

## 5. AI Job 生命周期与通用 Task 判断

### 5.1 建议的 AI Job 最小生命周期

第一份审计确认当前前端没有任何异步状态。若未来接入服务器侧 Provider，生成过程本身必然存在“已接收、调用中、终态成功/失败”的业务事实。因此方案建议在 AI Job Domain 内只确认最小状态：

```text
PENDING → RUNNING → SUCCESS
                  ↘ FAILED
```

- `PENDING`：Job 已被服务端接受，尚未开始 Provider 执行。
- `RUNNING`：服务端正在执行 Provider 调用。
- `SUCCESS`：所有预期结果已完成并持久化为 Asset。
- `FAILED`：本次生成未成功完成，保留安全失败摘要。

`CANCELLED` 不列入 V1：现有前端没有取消入口，也没有产品或 Provider 取消 Contract 的证据。重试、多图并发、进度百分比、部分成功、回调或轮询机制也不在本方案中预先定型。

### 5.2 不复用现有 Task Domain

本方案默认 **不** 把 AI Image Job 放入 `tasks`：

- 现有 `Task` 的核心语义是 `target_device_id + skill_id + Worker Claim + Lease`，由 Windows Worker 执行。
- 服务器直接调用 AI Provider 时没有目标设备、Worker Claim、Lease 或 Worker Token 的业务事实。
- 当前 `Task` 未接入 Access & Ownership Scope；把 AI 任务塞入该域会把尚未迁移的 Task Scope、设备资格和 Worker 生命周期引入 AI 生图，扩大范围且违背现有边界。

因此，AI 应有自己的业务 Job Domain，复用的是 Access、Assets、Storage 和通用分层方式，不复用 Worker Task 执行模型。若未来真实架构改为由 Worker 本地执行特定生成 Provider，需以新 Contract 重新评估，不能凭“统一任务中心”假设复用。

## 6. Frontend 接入方案

### 6.1 无需修改的部分

- 不新增 Team Picker、Creator Picker、SELF/TEAM/ALL 选择器或权限管理页面。
- 继续使用全局 Topbar 当前 Team、Auth Store 与统一 Axios Client 注入的 `X-Team-ID`。
- 继续由全局 Router Guard 处理未登录/未选择 Team 的页面体验。
- 继续使用 `resetQueriesForActorContextChange()`；当前 Team 切换会 `resetQueries()`，未来 AI Query 必须加入同一 Query Client，不能保留 Team A 的缓存到 Team B。
- 不建立 AI 专属 Storage、公开图片 URL 或前端直接读取服务器路径的机制。

### 6.2 Backend 接入时必须修改的部分

| 现有位置 | 必须替换或补齐的方向 |
|---|---|
| `AiGeneratePage.vue` | 将禁用 Prototype 改为真实表单状态、提交行为、任务状态与结果区域；字段必须等待正式 DTO 后再实现 |
| AI Workbench API 层 | 在 Feature/Entity 合适边界增加类型化 API Client 与 DTO Mapper；不得猜 URL/字段 |
| AI Workbench 数据层 | 使用 TanStack Vue Query 管理任务创建、详情/历史查询、状态刷新与 Team 切换缓存失效 |
| 素材选择 | 使用正式 Asset 数据源和 Asset 标识；不使用 Fixture URL、浏览器 Object URL 或仅名称作为引用 |
| 模板选择 | 将模板管理持久化后再向生成表单提供选择与变量输入；当前生成页尚无此接线 |
| 结果展示 | 只消费 Backend 返回的 Job/Result/Asset 正式 Contract，通过既有认证内容读取方式展示图片 |

### 6.3 Backend 完成后删除的 Mock

- `templates/__fixtures__/template-groups.fixture.ts` 与 `useAiTemplatesVisualMock.ts` 的模板 Fixture/内存 CRUD。
- `assets/__fixtures__/product-material-groups.fixture.ts` 与 `useAiAssetsVisualMock.ts` 的伪造 assetId、SVG data URL、Object URL 上传与内存分组操作。
- 两个 `visual-mock-gate.ts` 与仅用于 Visual Mock 的异步组件加载分支，应在真实页面完成并验收后移除或替换。

删除顺序应按真实 API/DTO 和页面 Query 就绪后进行，不能因页面尚未接线而先删除可供视觉回归验证的 Mock。

## 7. Backend 模块规划

未来新模块建议遵守现有模块化单体层级：

```text
AI Image API
↓
AI Image Service
├─ AI Image Repository
├─ AssetService（参考素材 Scoped Lookup、生成 Asset 创建）
└─ AI Provider Adapter
↓
AI Image Job / 生成结果关系
↓
PostgreSQL
```

| 层 | 未来职责 | 不承担的职责 |
|---|---|---|
| API | Human `ActorContext` 依赖、DTO 解析、调用 Service、返回正式 Contract | 不写 Job 表、不做 Scope SQL、不直调 Provider |
| Service | Ownership 赋值、参考 Asset 校验、生命周期、事务边界、Provider 与 AssetService 编排 | 不信任前端 Team/User，不在此重做通用 Scope 策略 |
| Repository | Job/结果的查询、写入、锁、分页；用 `DataScopePolicy` 查询历史 | 不做权限文案、Provider 调用或 UI 逻辑 |
| Provider Adapter | Provider 请求/响应、可重试错误分类和外部协议适配 | 不持久化 Ownership、不会绕过 AI Service 建 Asset |
| Job Model | 表达一次生成过程、Ownership、生命周期与结果关联 | 不充当文件表，不保存 Asset 的 Storage 内部信息 |
| DTO | 对齐经过确认的生成、状态、结果 Contract | 不暴露 `team_id` / `created_by_user_id` 的前端写入入口 |
| Migration | 在最新 Main Head 后创建 AI Job 所需最小结构 | 不顺带迁移 Task/Shop/Schedule Scope |
| Tests | 身份、Scope、Asset 越权、生命周期、Provider/Storage 失败、API Contract | 不以 Mock 绕过 Service 层 |

Provider Credential / Model Config 应作为系统基础设施配置接入点，不属于 Employee Ownership；当前仓库尚未存在 AI Provider Contract，因此 Provider 名称、模型字段、配置位置和密钥管理方式均保持待确认。AI Job 未来可记录经过确认的 Provider/Model 生成事实，但不在本 V1 最小字段中预置。

## 8. 数据库规划（最小业务事实）

以下仅列出 Access & Ownership 强制需要，以及当前前端已明确会产生的“生成请求、状态、结果、参考素材”事实；不是最终表设计。

### 8.1 AI Image Job 必须表达

| 业务事实 | 来源 |
|---|---|
| 稳定 Job 标识 | 生成请求、结果追踪与未来历史读取的基础 |
| `team_id` | Access & Ownership Foundation 的 Team 数据边界 |
| `created_by_user_id` | SELF Scope 与“谁创建”事实 |
| 最小生命周期状态 | 服务器 Provider 过程的 PENDING/RUNNING/SUCCESS/FAILED 方案 |
| 创建时间 | 第一份审计明确列出的未来生成业务事实 |
| 完成时间 | 第一份审计明确列出的未来生成业务事实 |
| 安全失败信息 | 第一份审计明确列出的未来生成失败事实 |

### 8.2 关联事实必须表达

| 关联 | 原因 |
|---|---|
| Job ↔ Reference Asset | 生成输入需要可验证的参考素材，且一项素材可能被多次生成复用 |
| Job ↔ Generated Asset | 一次生成可能有一个或多个最终媒体结果；Asset 是统一媒体事实 |

当前 Visual Mock 中的模板组、模板、商品素材分组、素材角色需要在其正式管理 Contract 被确认后，再决定具体模型和关系。不能用 Mock 的 `visual-*` ID、`previewUrl`、SVG、前端枚举或 `URL.createObjectURL` 直接作为数据库设计。

本阶段不预置 Provider 参数 JSON、模型名、尺寸、质量、种子、计费、Webhook、重试次数、取消原因或第二套文件表；这些没有来自当前正式 Frontend 的确定 Contract。

## 9. Migration 与 Worktree 同步计划

### 9.1 从最新 Main 开始

当前审计所在分支为 `main`，最新提交为 `8073264 merge: integrate Asset Scope V1`。当前最新 Alembic Head 是：

```text
20260901_0024_asset_scope_v1
down_revision = 20260831_0023
```

AI Backend 实施开始前，AI Worktree 必须先同步最新 `main`，再读取当时的真实 Alembic Head。新 Migration 必须从那个同步后的 Head 延伸，不得依据旧 AI Worktree 的历史 Head 编写。

### 9.2 Worktree 保护步骤

若 AI Worktree 有未提交内容：

```text
检查 git status
↓
提交当前 AI 成果或创建可恢复 Snapshot
↓
确认 Worktree clean
↓
同步最新 main
↓
解决并验证必要冲突
↓
读取同步后的真实 Alembic Head
↓
创建 AI Migration
```

禁止使用 `git reset --hard` 清理 AI Worktree，避免丢失既有 Frontend 成果。共享开发数据库也不能为了单个功能分支验证而直接升级；需遵循现有隔离测试数据库/临时 Schema 规则。

## 10. 权限与 Access Management 边界

AI 模块不得自建：

- AI User、AI Team、AI Membership、AI Session；
- AI Data Scope、AI Asset Permission、AI Ownership 规则；
- AI Role、AI Permission Database 或 AI Permission UI；
- 独立 Team Picker、Creator Picker 或 Scope Picker。

未来“系统设置 → 用户与权限”中的 Access Management / Permission Registry 可能提供 `ai.image.use`、`ai.image.read`、`ai.image.delete` 等功能权限。届时 AI API 只在 API 边界消费统一权限判断结果，AI 页面只消费 Backend 返回的可用性与数据；AI Domain 不负责配置 Membership、Role 或功能权限。

在统一 Permission 体系未完成前，AI Backend 不应因等待完整 Access Management UI 而阻塞；它可以先完整复用现有 Human Auth、ActorContext、DataScopePolicy 与 Asset Scope。

## 11. 建议实施阶段

### A. AI Domain Foundation

- 新建 AI Image Job Domain 的 Model/Repository/Service/API 骨架和最小 Contract。
- API 从 `ActorContext` 建立 Job Ownership；实现 Job 历史 Scope 查询。
- 不接 Provider，不接 Worker，不接前端真实生图按钮。

### B. Reference Asset Integration

- 在 Job 创建事务边界前调用正式 Scoped Asset Lookup。
- 覆盖 UUID 猜测、跨 Team、SELF/TEAM/ALL、缺失引用和重复引用的测试。
- 不接受前端 Owner/Team/本地路径作为替代。

### C. Provider 与最小生命周期

- 在 Provider Contract 明确后添加 Adapter。
- 实现 PENDING/RUNNING/SUCCESS/FAILED 的状态变化、幂等策略和安全失败摘要。
- 根据真实 Provider 调用方式再确认同步、后台执行、回调或轮询，不预先绑定 Redis/Worker。

### D. Generated Asset Persistence

- Provider 成功结果经 `AssetService.create` 进入统一 Asset Storage。
- 结果 Asset 继承 Job Ownership，使用 `AI_GENERATED`。
- 覆盖 Provider 成功但 Storage/数据库失败的补偿与一致性行为。

### E. 模板与素材管理持久化

- 依据现有 Visual Mock 的用户交互确认模板、商品素材分组与角色的正式 Contract。
- 只在 Contract 确认后实现相应管理 API 和关系；不把前端 Fixture 当 schema。

### F. Frontend Real API Migration

- 为真实模板、素材选择、生成创建、状态/结果/历史引入 API Client 与 Vue Query。
- Team 切换时复用全局 Query reset，验证不串 Team 数据。
- 完成替换后逐步移除 Visual Mock 与 gate，并补齐单元、组件、端到端测试。

Task Scope、Schedule Scope、Shop Scope、Mobile Auth、完整 Access Management UI 不应阻塞上述 A-D，除非未来正式 AI Contract 明确需要它们。

## 12. 风险与防护

| 风险 | 当前依据 | 方案防护 |
|---|---|---|
| Mock 与正式 Contract 差距 | AI 页面目前无真实生成请求；模板/素材仅内存 Mock | 先确立 DTO/交互 Contract，再迁移页面；不以 Fixture 字段建库 |
| 旧 AI Worktree 落后 Main | Access / Asset Scope 刚在 Main 集成 | 先 Snapshot/Commit、确保 clean、同步 Main、再从真实 Head 建 Migration |
| Reference Asset 越权 | Frontend Mock 使用可伪造的本地标识；Asset 已支持 Scope Lookup | Job 创建前使用 `list_accessible_by_ids` 并核对完整集合，缺失即 Fail Closed |
| 重复点击与生成幂等 | 现有生成页无提交状态 | Provider 接入阶段明确请求幂等 Contract；不能只依赖前端按钮禁用 |
| 多图生成语义 | Mock 模板有 `count`，生成页未接线 | 在正式请求 DTO/结果关联确认前，不把 Mock 范围当 Provider 能力 |
| Provider 错误 | 当前无 Provider Adapter/错误 Contract | Adapter 分类外部错误，Service 保存安全失败摘要；不泄漏密钥或原始敏感响应 |
| Provider 成功、Storage 失败 | Asset 创建与 Job 完成是跨外部边界 | Service 明确持久化顺序、失败补偿/恢复策略并测试 |
| Team 切换串数据 | AI 尚未有 Query；全局已有 resetQueries | 所有未来 AI Query 使用同一 Query Client，Team 切换统一 reset 后重新读取 |
| 把 AI 放入 Worker Task | 现有 Task 强依赖设备/Skill/Lease | 服务器 Provider 使用独立 AI Job，仅复用通用底座 |

## 13. Blocking Questions

以下问题现有代码无法回答，实施前必须由产品/Provider Contract 明确：

1. 第一版采用哪个 AI Provider、以何种认证方式和调用模式执行。
2. 生成请求最终允许哪些输入：模板、正/负提示词、商品素材、参考素材、比例、数量及其约束。
3. 结果是一张还是多张；多结果是否允许部分成功，以及 Job 的成功定义。
4. 生成执行是同步等待、后台服务运行、Provider 回调还是客户端轮询。
5. 是否进入 V1 的历史、重新生成、取消、重试、批量或并发体验。
6. 模板组、商品素材分组和素材角色是否是正式业务实体，以及其与通用 Asset 的关系。
7. Provider / Model 生成事实需要在 Job 中记录到何种粒度，及其保留与审计要求。

## 14. Git

本次仅新增方案文档和索引，不修改生产代码。

**Production Code：0 变化。**
**Migration：0 新增。**
