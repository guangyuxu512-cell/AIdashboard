# AI Workbench Backend Contract V2

> - 状态：管理数据契约已确认，存在一项 Migration 前阻塞问题
> - 确认日期：2026-09-02
> - 范围：AI Template Library、AI Assets / Product Material Group 的 Backend Management Persistence Foundation

## 1. 文档定位

本文是 AI Workbench 管理数据的当前 Backend Contract。以下文档继续保留为历史审计，不改写其当时结论：

- `frontend/docs/13-AI生图模块现状与后端接入需求 V1.md`
- `frontend/docs/14-AI生图接入Access与Ownership Foundation V1方案.md`

V2 的业务事实来自当前冻结的 Frontend Types、Visual Mock 行为和 Tests；Backend 接法来自当前正式的 Access、Asset、API、Service、Repository、DTO、分页和错误处理模式。Access/Ownership 关系规则同时接受已经进入 `dev` 的提交 `54993baca7b4600df930c997bb5c542659764f22`。

本文只确认拿到 Migration Slot 后要实现的管理数据契约，不创建 Migration、数据库、SQLAlchemy Model、Repository、Service 或 API。

## 2. 本阶段边界

本阶段计划持久化五类业务对象或关系：

1. `TemplateGroup`
2. `PromptTemplate`
3. `ProductMaterialGroup`
4. `MaterialGroupAsset`
5. `MaterialGroupTemplateBinding`

本阶段不实现：

- `GenerationJob`、`GenerationItem` 或任何生成状态机
- Provider / ToAPI Adapter、Provider 配置或密钥
- Queue、Polling、Webhook、Retry Backend
- AI 专属文件表、上传 API 或 Storage
- Frontend Real API Migration
- Visual Mock 删除
- AI 专属 User、Team、Membership、Data Scope 或 Asset Permission

当前冻结前端已经具备即时生成、批量生成、结果、记录和重试的 Visual Mock；生成配置只有一个 `prompt`。即时生成成功结果由用户显式加入产品素材，批量生成成功结果自动归入计划对应产品。这些是后续 Generation Backend 的输入事实，不是本管理数据 Feature 的持久化范围。

## 3. 统一枚举

### 3.1 Generation Mode

- `NORMAL_GENERATION`：普通生图
- `STYLE_REPLICATION`：风格复刻

### 3.2 Output Role

- `MAIN_IMAGE`：主图
- `DETAIL_IMAGE`：详情

### 3.3 Output Format

- `SINGLE`：单图
- `COLLAGE_2X2`：四宫格

### 3.4 Generation Size

- `1:1`
- `3:4`
- `4:3`
- `16:9`

### 3.5 Material Role

- `PRODUCT_SOURCE`：商品素材
- `STYLE_REFERENCE`：复刻参考
- `AI_OUTPUT`：AI 成品

这些值来自当前共享 Frontend Types。Backend 实现不得另建含义相同但取值不同的 AI 私有枚举。

## 4. Ownership 与 Scope

### 4.1 聚合根

`TemplateGroup` 与 `ProductMaterialGroup` 是 Team Scoped 聚合根，持久化时必须包含：

- `team_id`
- `created_by_user_id`

创建时两者均由 `ActorContext` 派生，公开创建或更新 DTO 不接受 `team_id`、`created_by_user_id`、`owner_user_id` 或 `data_scope`。

`PromptTemplate` 通过所属 `TemplateGroup` 继承 Scope；`MaterialGroupAsset` 与 `MaterialGroupTemplateBinding` 通过所属 `ProductMaterialGroup` 继承 Scope。本阶段没有事实要求在这些子对象或关系上冗余 Ownership 字段。

### 4.2 读取与写入

聚合根列表和详情必须复用 `DataScopePolicy`：

- `SELF`：当前 Team 且创建人为当前 User。
- `TEAM`：当前 Team。
- `ALL`：不追加 Ownership 读取条件。
- 非法 Scope：Fail Closed，返回 `INVALID_DATA_SCOPE`，HTTP 500。

`ALL` 只扩大读取范围，不允许跨 Team 创建、更新、删除、转移或建立关系。所有写操作都以当前 `ActorContext.team_id` 为 Team 边界。

子对象的详情、更新、删除和排序必须先解析一个当前写入边界内的父聚合根，不能只凭子对象 UUID 操作。

## 5. TemplateGroup Contract

### 5.1 持久化字段

| 字段                 | 契约                                       |
| -------------------- | ------------------------------------------ |
| `id`                 | 稳定 UUID                                  |
| `team_id`            | Team Ownership，来自 `ActorContext`        |
| `created_by_user_id` | Creator Ownership，来自 `ActorContext`     |
| `name`               | trim 后 1–100 字符                         |
| `mode`               | `NORMAL_GENERATION` 或 `STYLE_REPLICATION` |
| `enabled`            | 启用状态                                   |
| `created_at`         | 创建时间                                   |
| `updated_at`         | 更新时间                                   |

一个模板组只属于一种 `mode`。当前创建流程选择 `mode`，后续编辑只支持名称和启用状态，因此 `mode` 创建后不可修改。

创建时当前 Frontend 默认 `enabled = true`。`enabled = false` 只表示模板组不可参与未来生成执行，不删除组内模板，也不删除产品素材组绑定。

当前冻结契约没有模板组名称唯一性规则，Backend 不得把名称唯一性作为隐含业务规则。

## 6. PromptTemplate Contract

### 6.1 持久化字段

| 字段                | 契约                                 |
| ------------------- | ------------------------------------ |
| `id`                | 稳定 UUID                            |
| `template_group_id` | 所属 `TemplateGroup`                 |
| `name`              | trim 后 1–100 字符                   |
| `enabled`           | 启用状态                             |
| `output_role`       | `MAIN_IMAGE` 或 `DETAIL_IMAGE`       |
| `output_format`     | `SINGLE` 或 `COLLAGE_2X2`            |
| `size`              | 当前四种 `Generation Size` 之一      |
| `count`             | 整数，1–8                            |
| `variables`         | 最多 20 个 trim 后非空、去重的变量名 |
| `prompt`            | trim 后 1–5000 字符                  |
| `sort_order`        | 所属组内连续稳定顺序                 |
| `created_at`        | 创建时间                             |
| `updated_at`        | 更新时间                             |

当前业务只有一个 `prompt`。`negative_prompt` / `negativePrompt` 不属于当前业务字段，不得重新加入。Provider 若未来需要额外指令，由后续 Provider Adapter 处理。

`variables` 只保存模板变量名称集合，不保存具体产品名、卖点、场景或其他运行时值。物理 SQL 类型留到获得 Migration Slot 后按 PostgreSQL 与当前 Model 规范确定，不在无 Migration 审查的文档阶段猜测。

### 6.2 创建与编辑语义

- 新建主图模板：`output_role = MAIN_IMAGE`，Frontend 默认 `output_format = SINGLE`、`size = 1:1`、`count = 1`、`variables = [product_name]`、`prompt = {product_name}`。
- 新建详情模板：`output_role = DETAIL_IMAGE`，Frontend 默认 `output_format = SINGLE`、`size = 3:4`、`count = 1`、`variables = [product_name]`、`prompt = {product_name}`。
- `output_role` 在创建入口确定，当前编辑器不提供修改能力，因此创建后不可修改。
- `size` 可独立修改，不能根据比例反推或改变 `output_role`。
- 复制模板保留源模板的 `enabled`、`output_role`、`output_format`、`size`、`count`、`variables` 和 `prompt`，生成新 UUID、复制名称和新的时间字段。

上面的默认值是当前 Frontend 创建契约；Backend create DTO 仍应显式校验并保存调用方提交的业务字段，不依赖 UI 才能保证合法性。

### 6.3 排序语义

同一 `TemplateGroup` 只有一条连续 Template Sequence：

1. `MAIN_IMAGE` 在前。
2. `DETAIL_IMAGE` 在后。
3. 每个角色内部按 `sort_order` 升序。
4. 新建、删除、复制和 reorder 后顺序必须重新归一为连续值。
5. 上移或下移只在相同 `output_role` 内发生，不改变角色。

reorder 是 Service 事务；Repository 负责锁定、更新和持久化，不由 API Handler 逐条直写。

## 7. ProductMaterialGroup Contract

### 7.1 持久化字段

| 字段                        | 契约                                   |
| --------------------------- | -------------------------------------- |
| `id`                        | 稳定 UUID                              |
| `team_id`                   | Team Ownership，来自 `ActorContext`    |
| `created_by_user_id`        | Creator Ownership，来自 `ActorContext` |
| `name`                      | trim 后 1–100 字符                     |
| `enabled`                   | 产品素材组总启用状态                   |
| `normal_generation_enabled` | 普通生图启用状态                       |
| `style_replication_enabled` | 风格复刻启用状态                       |
| `created_at`                | 创建时间                               |
| `updated_at`                | 更新时间                               |

当前 Frontend 以 `normalTemplateGroupIds` 与 `styleReplicationTemplateGroupIds` 表达绑定集合；Backend 使用 `MaterialGroupTemplateBinding` 关系表达，不把 ID 数组作为聚合根字段存储。

当前冻结契约没有 SKU。V2 不新增 `sku` 或其他产品主数据字段，也不把产品素材组改造成商品中心实体。

创建时当前 Frontend 默认：

- `enabled = true`
- `normal_generation_enabled = true`
- `style_replication_enabled = false`
- 两类模板绑定均为空

将 `enabled`、`normal_generation_enabled` 或 `style_replication_enabled` 设为 `false`，都只改变可执行性，不删除 Asset 关系或 Template Binding；重新启用后原关系仍存在。

## 8. MaterialGroupAsset Contract

`MaterialGroupAsset` 是 `ProductMaterialGroup` 与统一 `Asset` 的业务关系，至少表达：

| 字段                | 契约                                               |
| ------------------- | -------------------------------------------------- |
| `material_group_id` | 所属 `ProductMaterialGroup`                        |
| `asset_id`          | 现有 Asset Foundation 的 `Asset.asset_id`          |
| `role`              | `PRODUCT_SOURCE`、`STYLE_REFERENCE` 或 `AI_OUTPUT` |
| `created_at`        | 关系创建时间                                       |

同一 Asset 在同一产品素材组中只有一个当前 `role`；重复 attach 不创建重复关系。当前普通角色变更只允许 `PRODUCT_SOURCE` 与 `STYLE_REFERENCE` 互换，不能通过素材管理操作把 Asset 改入或改出 `AI_OUTPUT`。`AI_OUTPUT` 由后续真实生成归档流程建立，本阶段不实现该流程。

Frontend `MaterialAssetReference` 中的 `name`、`mediaType`、`sourceType`、`previewUrl`、尺寸和字节数是 Asset 读取投影，不是关系字段；`objectUrl` 是 Visual Mock 生命周期标记。可选 `generationMode` 目前只存在于 AI 成品 Fixture，没有正式持久化写入或归属事实，因此 V2 不新增该列，由后续 Generation Backend 定义其权威来源。

Frontend 展示来源值 `LOCAL_UPLOAD`、`MATERIAL_IMPORT`、`AI_GENERATION` 对应现有 Asset Foundation 的 `upload`、`imported`、`ai_generated`。持久化继续使用正式 `Asset.source_type`，不在关系表复制另一套来源枚举。

AI 不创建 `ai_files`、`ai_images`、`material_files` 或 `provider_images`。关系不得保存 `storage_key`、bucket、服务器绝对路径或厂商图片 URL。内容与预览继续走 Asset Content 边界。

## 9. Asset Attach / Detach 与 Access

attach 必须由 `ProductMaterialGroup` Service 协调现有 `AssetService` Scoped Lookup：

1. 在当前 Actor 的写入边界内解析产品素材组。
2. 通过现有 Asset Service 查询调用者可读的 Asset。
3. 额外验证 `asset.team_id = product_material_group.team_id`。
4. 同一事务内创建或更新关系。

即使 Actor 具有 `ALL` 并能读取其他 Team 的 Asset，也不能把它关联到当前 Team 的产品素材组。不得在 AI Repository 复制一套 Asset 权限 SQL。

正式错误语义：

- Asset 不存在、不可读或属于错误 Team：统一 `ASSET_NOT_FOUND`，HTTP 404。
- Actor 无权选择请求中的 Team：`TEAM_ACCESS_DENIED`，HTTP 403。
- 非法 Data Scope：`INVALID_DATA_SCOPE`，HTTP 500。

detach 只删除 `MaterialGroupAsset` 关系，不删除 Asset 本体或 Storage 对象。

## 10. MaterialGroupTemplateBinding Contract

关系至少表达：

| 字段                | 契约                        |
| ------------------- | --------------------------- |
| `material_group_id` | 所属 `ProductMaterialGroup` |
| `generation_mode`   | 绑定槽位的模式              |
| `template_group_id` | 被绑定的 `TemplateGroup`    |
| `position`          | 同模式绑定集合内的稳定位置  |
| `created_at`        | 关系创建时间                |

规则：

- `generation_mode = NORMAL_GENERATION` 只能绑定 `TemplateGroup.mode = NORMAL_GENERATION`。
- `generation_mode = STYLE_REPLICATION` 只能绑定 `TemplateGroup.mode = STYLE_REPLICATION`。
- 被绑定模板组必须与产品素材组属于同一 Team；`ALL` 不扩大关系写入范围。
- 同一产品素材组内，同一模板组最多绑定一次；替换输入中的重复 ID 必须去重。
- `normalTemplateGroupIds` 与 `styleReplicationTemplateGroupIds` 都是有序集合；读取必须按 `position` 还原输入顺序，批量生成计划消费该顺序。
- replace/update 按输入中的首次出现顺序去重，并把每个 `(material_group_id, generation_mode)` 序列归一为从 0 开始的连续 `position`。
- 关闭生成模式或停用模板组不删除绑定。
- replace/update 必须在 Service 中完成模式、Team 和可访问父聚合校验，并在一个事务内替换关系集合。

关系使用标准关系模型，不以 JSON ID 数组保存。唯一性至少保证同一产品素材组内模板组不重复，以及同一产品素材组、模式和位置不重复；`position` 必须非负。字段与事务模式复用现有有序关系的正式 Pattern。物理主键、外键 `ondelete` 和索引在获得 Migration Slot、同步最新 Green `dev` 并解决第 15 节问题后确定。

## 11. 删除语义

### 11.1 PromptTemplate

删除模板会删除该模板，并重新归一所属组剩余模板的 `sort_order`。不存在回收站、版本历史或 `deleted_at` 的冻结需求。

### 11.2 ProductMaterialGroup

删除产品素材组会删除该聚合及其 `MaterialGroupAsset`、`MaterialGroupTemplateBinding` 关系。绝不能因此删除 Asset 本体或 Storage 对象。

### 11.3 Asset Relation

单个或批量“删除素材”的当前管理语义在 Backend 中是 detach 关系，不是删除 Asset Foundation 中的 Asset。真正删除 Asset 只能继续通过 Asset Foundation 的正式删除边界与引用保护规则。

### 11.4 TemplateGroup

当前模板 Visual Mock 删除组时会删除本地组及其子模板，但 Template Mock 与 Product Material Mock 是两个独立 Store，无法证明一个已被 `MaterialGroupTemplateBinding` 引用的模板组应当被拒绝删除，还是应在同一事务内先移除绑定。该行为是第 15 节唯一 Migration 前阻塞问题。

## 12. API 能力清单

本轮只锁定能力，不锁定最终 URL、HTTP Method 或 DTO 类名。

### 12.1 Template Group

- list：按 Scope、模式、启用状态及当前搜索需求查询并分页。
- detail：返回可访问组及其模板序列。
- create：由 ActorContext 写 Ownership。
- update：名称和启用状态；不修改模式。
- delete：遵守第 11、15 节。

### 12.2 Prompt Template

- create：在可写父组下创建，角色创建后固定。
- update：更新可编辑字段，不改变角色或所属组。
- delete：删除并归一顺序。
- reorder：同角色内事务性重排。

### 12.3 Product Material Group

- list：按 Scope、启用状态及当前搜索需求查询并分页。
- detail：返回管理字段、Asset 关系和模板绑定。
- create：由 ActorContext 写 Ownership。
- update：名称及三类启用状态。
- delete：删除聚合关系，不删除 Asset。

### 12.4 Relations

- Asset attach / detach。
- Template Binding read / replace-update。

列表统一复用 `Page[T]` 与 `PaginationParams`：默认 `page = 1`、`page_size = 20`，最大 100；Scoped Count、排序和分页必须基于同一过滤结果。

## 13. Backend Pattern 映射

### 13.1 API

- 使用现有 FastAPI `APIRouter`、`/api/v1` 注册体系和依赖注入。
- Router 只解析 HTTP Contract、获取 `ActorContext` 并调用 Service。
- 使用现有 `COMMON_ERROR_RESPONSES` 与统一错误 Envelope。
- 不在 Handler 内写 SQL、操作 ORM Entity 或实现 Scope 过滤。

AI API 的最终资源路径和 DTO 名称尚无现存模块事实，本轮不写死；实现时按当时最新 Backend 模块注册模式确认。

### 13.2 DTO

- 使用 Pydantic DTO，与 ORM Model 分离。
- 输入 DTO 使用当前 `extra="forbid"`、trim 和字段/组合校验模式。
- 创建/更新 DTO 不接受 Ownership、Storage 或内部 Asset 字段。
- Read DTO 只返回前端业务所需投影，不返回 `storage_key`、bucket、Secret 或数据库实现细节。

AI 聚合自身的具体 Not Found / Conflict 错误码名称尚未存在，本轮不发明；必须在 API 实现前按统一 `AppError` 规范正式定义。该命名不影响管理表 Migration 设计。

### 13.3 Service

Service 是业务规则与事务边界，负责：

- 从 ActorContext 派生 Ownership。
- 协调聚合根 Scope 和写入 Team 边界。
- 调用 AssetService 做 Asset Scoped Lookup。
- 校验 Template Mode、同 Team 关系、Enabled 保留关系语义。
- 执行 reorder、关系 replace 和删除事务。

### 13.4 Repository

Repository 只负责 SQLAlchemy 查询、锁、写入、计数、排序、分页与关系持久化。聚合根查询接入 `DataScopePolicy`；子对象与关系从已 Scoped 的父聚合进入，不自行解释 Frontend 文案或跨 Domain 流程。

### 13.5 Model 与 Migration

获得 Migration Slot 后使用当前项目的 SQLAlchemy 2、稳定 UUID、`TimestampMixin`、显式约束与查询驱动索引模式。只为以下真实查询设计约束和索引：

- Team / Creator Scoped 聚合列表。
- TemplateGroup 的子模板顺序。
- MaterialGroup 的 Asset 关系查询。
- MaterialGroup 的 Template Binding 查询与反向引用检查。

不得预先为所有字段加索引，不得自编号 Revision，不得连接 `control_center_dev` 或 `control_center_integration` 做 Feature 写入。

## 14. 实施与测试计划

获得 Migration Slot、Feature DB 并解决第 15 节后，最小实施顺序为：

1. 从最新 Green `dev` 确认 Alembic Head、正式 Access / Asset API 和模块命名。
2. 创建五类管理数据 Model / 关系及唯一约束、外键和必要索引。
3. 实现 Repository 的 Scoped list/detail、子序列、关系查询和事务写入。
4. 实现 Service 的 Ownership、Mode、same-Team Asset、绑定、排序和删除规则。
5. 实现 Pydantic DTO 与最小 API 能力，不创建通用 CRUD 框架。
6. 在 Feature DB 验证 Migration，并完成 Backend Unit、API Contract、Security、Data Scope、Ownership 与 Asset Boundary Tests。

测试至少覆盖：

- Ownership 只能来自 ActorContext，客户端无法覆盖。
- `SELF`、`TEAM`、`ALL` 的 Scoped list/detail。
- `ALL` 下跨 Team update/delete/attach/bind 仍被拒绝。
- Asset 不存在、不可读、错误 Team 的统一 404 语义。
- 重复 Asset attach 不产生重复关系；detach 后 Asset 仍存在。
- Normal / Style 模式绑定校验和同 Team 校验。
- Template Binding replace 去重后仍保留首次出现顺序，并返回连续稳定的 `position`。
- 关闭产品、生成模式或模板组不清除既有关系。
- PromptTemplate create/delete/duplicate 所需数据与 reorder 的连续稳定顺序。
- Template / Product list 的过滤、Scoped total 和 Pagination 一致。
- 删除 ProductMaterialGroup 后 Asset 本体仍存在。
- DTO 不接受 Ownership，不返回 Storage 内部字段。

## 15. Blocking Question

**删除仍被 ProductMaterialGroup 绑定的 TemplateGroup 时采用哪一种正式行为？**

- 阻止删除并返回统一 Conflict；或
- 在同一事务内删除所有 `MaterialGroupTemplateBinding` 后再删除模板组与子模板。

当前冻结的两个 Visual Mock Store 相互独立，现有 Backend 也没有该业务关系，无法从真实代码、测试或 Contract 判定。该选择会直接决定外键 `ondelete`、Service 删除事务和错误契约，因此在创建 Migration 前必须由产品 / 架构确认，本文不设默认答案。

## 16. Readiness

`READY FOR MIGRATION SLOT: NO`

真实阻塞仅为第 15 节的 TemplateGroup 被绑定时删除语义。除此之外，管理数据字段、枚举、Ownership、Scope、Asset same-Team 关系、Enabled 保留语义、排序、API 能力和分层接法均已确认。

当前仍没有 AI Migration Slot，也没有 AI Feature DB。阻塞问题确认后，下一步才是申请 Migration Slot 与 Feature DB；本轮没有创建或占用二者。
