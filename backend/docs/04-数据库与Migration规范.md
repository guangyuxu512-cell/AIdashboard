# 数据库与 Migration 规范

数据库渐进式演进，不要求一次设计所有表。

新需求先判断：

- 新属性
- 新实体
- 新关系

## 主键

使用稳定 ID，禁止名称主键。

## 多对多

明确可能多对多时使用关系表。
例如 `shop_device_binding`。

## Migration

所有结构变化通过 Alembic。
禁止直接手改正式 DB。

## 索引

根据实际查询条件补索引，不无依据创建大量索引。

## 敏感数据

Credential / Session 与普通业务字段分离并加密。

## Core Domain V1 数据库

首个正式业务 Migration：`20260818_0001_core_domain_v1`。

| 表                     | 职责                                           |
| ---------------------- | ---------------------------------------------- |
| `users`                | 最小系统用户身份，供负责人等稳定关系引用       |
| `shops`                | 店铺基础事实、平台、启用状态、可选负责人和备注 |
| `devices`              | 设备身份、启用状态、可选位置和备注             |
| `shop_device_bindings` | Shop 与 Device 的执行资格多对多关系及启用状态  |

核心 ID 使用统一 UUID；核心表使用带时区的 `created_at`、`updated_at`。`shop_device_bindings` 使用 `(shop_id, device_id)` 复合主键防止重复关系。Binding 只表示执行资格，不表达主设备、备用设备或默认唯一设备；同一个 Shop 可以同时绑定多个 Device。

Migration `20260822_0008_shop_soft_delete` 为 `shops` 增加可空 `deleted_at` 与查询索引。`enabled=false` 只表示业务停用，`deleted_at IS NOT NULL` 才表示从正常业务视图移除；软移除不级联删除 Credential、ShopCredentialBinding、ShopSession、Task 或历史数据，`shop_id` 永不复用。

Shop 平台 V1 机器值仅包含 `douyin`、`pdd`。

## Authentication Domain V1 数据库

Migration `20260819_0002_auth_domain_foundation` 增加：

| 表                         | 职责                                                      |
| -------------------------- | --------------------------------------------------------- |
| `platform_credentials`     | 平台、统一登录标识、加密 Secret、验证码渠道与启用状态     |
| `shop_credential_bindings` | Credential 与 Shop 的可扩展关系；每 Shop 最多一个启用关系 |
| `shop_sessions`            | 每 Shop 当前 Session 元数据、乐观并发版本与加密 payload   |

外键统一 `RESTRICT`，避免无意级联删除认证事实。Session 版本必须为正整数，更新由 Service 使用条件更新原子递增。真实迁移闭环只能在可随时重建且已登记的非生产数据库执行：Feature 使用其临时/Feature DB，Integration 使用 `control_center_integration`，Main smoke 使用 `control_center_dev`。Migration Slot、升级/降级和 Gate 规则见根 `docs/engineering/03-数据库与Migration协作规范.md`。

## Device Provider Inventory

Migration `20260820_0005_provider_inventory` 增加
`device_provider_inventory`。它以 `(device_id, provider_code)` 为复合主键，只保存
每台设备、每个 Provider 最近一次上报快照。Provider 的未安装、版本不支持、需登录、
接口不可达和 ready 都是正常 Inventory 状态；上报这些状态不删除 Device Runtime。
`inventory_payload` 是外部 Provider Inventory 的专用 JSONB，并用对象类型约束，
不得演变为任意业务数据容器。当前影刀应用数组保留在该快照中，等真实 Skill 与 App
绑定或版本管理需求出现后再独立建模。

Migration `20260823_0011_automation_application_configs` 增加
`automation_application_configs`，以 `(provider_code, app_id)` 唯一保存通用自动化应用的
参数 Schema、默认值、来源和版本。V1 的 `schema_source=manual`，只支持 text/number/
boolean/select；不得把 Credential、Cookie、流程内容或任意 Provider 原始响应放入该表。

Migration `20260823_0012_device_skill_capabilities` 增加
`device_skill_capabilities`，以 `(device_id, skill_id)` 为复合主键保存 Worker Registry 的
最后一次完整快照。`runtime / provider_code / skill_version` 是可查询、可约束的正式列；
不得用 `skills_json` 代替关系模型。同步采用 snapshot replace，设备离线只保留最后已知记录，
不删除能力，也不把能力状态混入 Task Runtime。

## 阶段 3D-1 持久结构

- `devices.deleted_at`：Device 软移除时间，UUID 和历史引用不删除。
- `device_runtime.connection_status/offline_since`：持久化转换前状态，避免 Backend 重启制造重复离线通知。
- `notification_channels`：全局通知通道；Webhook URL 仅以 SecretCipher 密文保存。

Migration 对既有 Runtime 按当前 45 秒阈值回填状态，但回填过程不产生通知。

## Task Runtime Event

Migration `20260822_0010_task_runtime_events` 增加 `task_events`。它只保存 Task 运行事件
流水，不是通用日志平台。`(task_id, seq)` 唯一并建立同序查询索引；metadata 使用受限
JSONB 对象，不得保存 Cookie、Token、Credential 或完整敏感任务输入。

Migration `20260823_0013_task_execution_display_name` 为 `tasks` 增加非空
`execution_display_name` 快照。既有 Task 使用 `skill_id` 回填；新 Task 创建时，普通 Skill
保存 Capability `display_name`，`yingdao.app.run` 保存当时 Provider Inventory 中匹配的
Application 名称。该字段用于列表与历史稳定展示，Application 后续改名不得反向改变旧 Task。

Migration `20260824_0015_task_query_runtime_retention` 将 Task 与 Runtime Event 生命周期正式
分离：`tasks` 是长期执行历史，`task_events` 是默认保留 90 天的运行明细；日志清理不得删除
Task、Result 或安全 Error 摘要。`tasks.runtime_events_purged_at` 仅在实际删除过至少一条 Event
时写入，用于区分“从未产生日志”和“历史日志已清理”。

管理查询按 `created_at DESC, task_id DESC` 稳定排序，并以
`(created_at, task_id)`、`(target_device_id, created_at, task_id)`、
`(status, created_at, task_id)` 支持日期、设备和状态组合。Retention 通过 Terminal Task 的
`finished_at` 部分索引选择小批次，再按 `task_id` 删除 Event；PENDING/RUNNING 永不进入
Retention。Runtime Summary 使用 `(task_id, event_type, seq)`，实时与历史游标继续依赖
`(task_id, seq)` 唯一索引。新增索引必须以真实 PostgreSQL EXPLAIN 验证，不能机械扩展排列组合。

Worker Token 生命周期继续复用 `worker_device_credentials`，每个 Device 最多一条记录；本轮
不新增第二套 Token 表或明文列。签发/轮换仅替换 SHA-256 `token_hash`，撤销使用既有
`enabled=false`，明文永不落库。

Migration `20260825_0018_task_shop_account_context` 曾为 `tasks` 与 `schedules` 增加可空单
`shop_id` 外键。Migration `20260826_0019_multi_shop_task_context` 将它们迁移为有序、规范化的
`task_shops` 与 `schedule_shops`，把历史非空关系写为 `position=0` 后删除旧列，避免双重权威。
同一 Migration 同时删除 `shop_device_bindings.binding_role`、角色 Check 和“每店最多一个启用
PRIMARY”的部分唯一索引；全部既有 PRIMARY/BACKUP 行保留为普通绑定。账号明文仍不新增数据库
列，Task Claim 只在运行时按关系顺序从各 Shop 当前启用的 Credential 构建 Payload。

Migration `20260826_0020_image_assets_v1` 增加 `assets` 与 `task_assets`。`assets` 只保存稳定
图片元数据：原文件名、存储键、内容类型、字节数与 SHA-256；文件本体位于 Backend Settings
配置的本机目录，不进入 PostgreSQL。`task_assets` 使用 `(task_id, asset_id)` 复合主键，并以
`(task_id, position)` 唯一约束保存一次 Task 内的图片顺序。被任何现存 Task 引用的 Asset 禁止
删除，确保历史 Task 关系始终完整；图片集合不得写入 Task JSON 或万能 metadata 字段。

Asset Foundation V2 在原表上补充 `media_type` 与 `source_type`，历史数据基于当前全部为人工
上传图片的已知事实迁移为 `image / upload`。`media_type` 与 MIME `content_type` 分工：前者是
稳定业务类别，后者是文件真实内容类型。`assets` 不保存 Shop、Task 执行状态或 AI Job 过程；
`storage_key` 只属于 Backend Storage 内部事实。V2 移除数据库对三个图片 MIME 的专用约束，
但当前 Upload 与 Task→Worker images_dir 契约仍只接受经 Service 验证的 IMAGE；VIDEO 只是
表结构扩展点，尚未开放上传或执行传输。

## Access Foundation V1 数据库

Migration `20260831_0022_access_foundation_v1` 增加 `teams` 与 `team_memberships`。
Membership 使用独立 UUID 主键、`UNIQUE(team_id, user_id)`、User Membership 查询索引与两个
Active Lookup 部分索引，并以 RESTRICT 外键关联 Team 与 User。`data_scope` 的数据库 Check 只允许
`self / team / all`；`role_code` 是非空可扩展字符串，当前默认 Registry 只有 `member`。

上述 `role_code / data_scope` 以及后续 `membership_module_accesses` 是历史升级、审计和最小旧接口
兼容字段。超级账号＋团队授权 V1 后，普通成员的现行授权来自有效 Team 的模块、店铺和设备授权；新业务查询、
新 API 和新 UI 不得把这些历史字段重新作为授权来源。保留字段不等于允许批量清理或改变既有历史记录。

Migration 创建一个“默认团队”，并把升级时已经存在的全部 User 各回填一条启用 Membership：
`role_code=member, data_scope=team`。空 users 表同样可以升级。任何旧用户都不会自动获得 ALL。
Team 与 Membership 以 `enabled` 停用，不以 Hard Delete 作为主要生命周期操作。

Phase A 不修改 Shop、Asset、Task、Schedule 或 AI Job 的 Ownership。后续 Team Scoped 业务表的
统一语义是 `team_id=数据归属团队`、`created_by_user_id=创建者`；现有
`Shop.owner_user_id` 仍只表示负责人，不承担权限边界。

Migration `20260905_0029_device_task_human_access_v1` 将这对字段加到 `devices`、`schedules` 与
`tasks`，使用 `RESTRICT` 外键、Team/创建者查询索引和 `team_id NOT NULL`。升级时仅在数据库恰有一个
Team 时回填既有记录的 Team；无法可靠归属的历史创建者保持 `NULL`，多 Team 的歧义数据拒绝迁移。

Migration `20260920_0038_parameter_preset_historical_reference_deletion_v1` 为
`automation_parameter_presets` 增加可空 `deleted_at`，将名称唯一性改为仅对正常可用记录生效的
`(team_id, app_id, name) WHERE deleted_at IS NULL` 部分唯一索引。删除预设时保留其行及 Task / 已归档
Schedule 的历史参数快照；未归档 Schedule（无论是否启用）仍必须先更换配置或删除。创建 Task 或
Schedule 时只接受 `deleted_at IS NULL` 的预设。该 Migration 的降级在存在任何已逻辑删除预设时
Fail Closed，避免将历史引用与名称唯一性恢复为不一致状态；生产回退须先评估并处理该数据前置条件。

## AI Provider V1 数据库

Migration `20260905_0030_ai_provider_v1` 增加 `generation_provider_executions`。该表以
`generation_item_id` 为主键，一条 GenerationItem 最多保存一个当前 Provider Execution；只记录
`provider_code / external_task_id / attempt_count / created_at / updated_at`。Retry 为新 Attempt 重置并复用同一行，
不建立 Attempt 历史。`external_task_id` 可空，仅用于调用 Provider 前已经提交的 Durable Create Intent；创建
成功后立即更新同一行。恢复时当前 Attempt 的空 Task ID 必须 Fail Closed，不得再次 Create。
`attempt_count` 与 GenerationItem 当前次数共同保护旧 Provider 结果不得回写。

0030 不修改 `generation_jobs / generation_items`，不创建 Provider、Model、Payload、History 或 Queue 表，
也不保存 Provider 结果 URL。V1 的 Provider Code 只允许 `toapis`；Provider 配置和 Secret 只来自 Backend
运行环境。

## Access Management V1 数据库

Migration `20260902_0025_access_management_v1` 增加
`membership_module_accesses`，以 `(membership_id, module_code)` 复合主键保存一条 Team
Membership 可访问的正式 PC 模块。它通过 `RESTRICT` 外键依附 `team_memberships`，不新增密码、
Token、角色继承或任意 JSON 权限列。升级时为既有 Membership 回填当前正式模块代码以保持兼容；
不自动改变角色、Data Scope 或授予 `access_admin`。人员、Team、Membership 均维持启停模型，
不通过本期 Migration 增加 Hard Delete。

## AI Workbench Backend Foundation V1 数据库

Migration `20260903_0026_ai_workbench_backend_foundation_v1` 增加：

| 表                                 | 职责                                           |
| ---------------------------------- | ---------------------------------------------- |
| `template_groups`                  | Team Scoped 模板组聚合根                       |
| `prompt_templates`                 | 模板组内主图优先、详情随后的连续提示词模板序列 |
| `product_material_groups`          | Team Scoped 商品素材组聚合根                   |
| `material_group_assets`            | 商品素材组与统一 `assets` 的角色关系           |
| `material_group_template_bindings` | 商品素材组按生成模式绑定模板组的有序关系       |

聚合根使用 `team_id / created_by_user_id` 接入现有 Access & Ownership Foundation；关系表不复制
Ownership。模板顺序为组内从 1 开始的连续 `sort_order`，模板绑定位置为模式内从 0 开始的连续
`position`。Prompt 只保存一个 `prompt`，变量名集合使用受数组 Check 约束的 JSONB。

全部关系外键使用 `RESTRICT`。删除 ProductMaterialGroup 时由 Service/ORM 明确删除该聚合自己的
Asset 与 Template Binding 关系，但不删除 Asset 本体。删除 TemplateGroup 前由 Service 检查反向
Binding；仍被引用时返回领域冲突，不自动解除关系，也不依赖数据库 Cascade。0026 不创建
GenerationJob、Provider 或 Queue 表。

## 当前完整表清单（Feature 0039 基线）

以下清单已与登记的 `control_center_feat_operating_dashboard_data` 在 `20260922_0039` Head 的实际 PostgreSQL
introspection 核对（2026-09-22）：共 **44** 张表，含 Alembic 元数据表。它不是生产库状态的推断，生产是否已
应用 0039 必须在 Release Gate 单独核对。未有已批准保留期的表明确标为“待定”，文档整理本身不授权删除、改名
或迁移任何历史数据。

### 系统与身份/授权

| 表 | 用途、主键与关联 | 当前/历史状态与删除、保留规则 |
| --- | --- | --- |
| `alembic_version` | Alembic 当前 revision，PK `version_num`。 | 系统元数据；只能由 Migration 工具维护。 |
| `users` | 人员身份，PK `user_id`；被 Team、业务对象、Session、审计引用。 | 正常业务不级联物理删除；停用/历史保留由人员服务管理。 |
| `teams` | 业务团队，PK `team_id`。 | 空且无资源/业务引用的团队才可删除；有历史业务数据时停用/归档，绝不级联删业务数据。 |
| `team_memberships` | User–Team 关系，PK `membership_id`，FK `user_id → users`、`team_id → teams`。 | `enabled=false` 是历史关系；当前授权只看有效关系，保留历史审计。 |
| `team_module_accesses` | Team 可用模块，复合 PK `(team_id,module_code)`。 | 删除关系立即撤销当前模块授权；不删除 Team 或业务对象。 |
| `team_device_accesses` | Team 可用 Device，复合 PK `(team_id,device_id)`。 | 删除关系立即撤销当前设备访问；不删除共享连接配置或 Device。 |
| `team_shop_accesses` | Team 可用 Shop，复合 PK `(team_id,shop_id)`。 | 删除关系立即撤销当前店铺访问；不删除 Shop、Session 或历史数据。 |
| `membership_module_accesses` | 旧 Membership 模块关系，复合 PK `(membership_id,module_code)`。 | **历史兼容**；新授权不得依赖或写入，保留升级/审计数据，退出条件待兼容旧客户端完成后另定。 |
| `human_sessions` | Human 登录会话，PK `session_id`，FK `user_id → users`。 | 认证生命周期/失效清理；不承担业务历史保留，具体 TTL 由认证配置定义。 |
| `audit_logs` | 安全与管理审计，PK `audit_log_id`，可关联 actor/Team。 | 审计记录；当前保留期待定，不可因 Team/成员移除级联删除。 |

### 店铺、凭证与设备

| 表 | 用途、主键与关联 | 当前/历史状态与删除、保留规则 |
| --- | --- | --- |
| `shops` | 店铺主档，PK `shop_id`，可关联 `owner_user_id`。 | `deleted_at` 软移除且 `shop_id` 不复用；停用/移除不删凭证、Session、Task 或经营历史。 |
| `platform_credentials` | 加密平台凭证，PK `credential_id`。 | 独立于 Shop；绑定停用/解除不自动清除凭证，敏感数据处置规则待单独定义。 |
| `shop_credential_bindings` | Shop–Credential 关系，复合 PK `(shop_id,credential_id)`。 | 启停/解绑不级联删任一事实；当前每 Shop 最多一个启用关系。 |
| `shop_sessions` | 每 Shop 当前加密 Session 与版本，PK `session_id`，FK Shop/来源 Device。 | 替换时以版本校验更新；软移除 Shop 后保留，不能导出明文 Cookie。 |
| `shop_device_bindings` | Shop–Device 执行资格，复合 PK `(shop_id,device_id)`。 | 普通可启停多对多；无 PRIMARY/BACKUP，停用绑定不删除历史 Task。 |
| `devices` | 设备主档，PK `device_id`，可关联 Team/创建人。 | 软移除；保留 Device ID 与历史 Task/审计显示。 |
| `worker_device_credentials` | Worker Device Token 摘要，PK `credential_id`，FK Device。 | 轮换覆盖 hash、撤销用 `enabled=false`；明文永不落库。 |
| `device_runtime` | 每 Device 当前运行快照，PK/FK `device_id`。 | 当前态可覆盖；不承担 Task Event 历史。 |
| `device_provider_inventory` | Device Provider 最新完整快照，复合 PK `(device_id,provider_code)`。 | snapshot replace；离线保留最后已知状态，不用删除表示离线。 |
| `device_skill_capabilities` | Device Skill 最新能力，复合 PK `(device_id,skill_id)`。 | snapshot replace；能力变化不回写旧 Task 快照。 |
| `notification_channels` | 全局通知通道，PK `channel_id`。 | 配置生命周期由通知服务管理；密文保留，历史/清理期限待定。 |

### 自动化、任务与计划

| 表 | 用途、主键与关联 | 当前/历史状态与删除、保留规则 |
| --- | --- | --- |
| `automation_application_configs` | 应用字段 Schema/默认值目录，PK `config_id`。 | 当前应用契约；移除/变更须先验证旧预设、Task/Schedule 快照兼容，不能自动级联清理。 |
| `automation_parameter_presets` | Team+应用参数预设，PK `preset_id`，FK Team/创建人。 | `deleted_at` 逻辑删除；历史 Task 和已归档 Schedule 可读，未归档 Schedule 仍引用时阻止删除。 |
| `tasks` | 长期 Task 历史与参数快照，PK `task_id`，FK Team/Device/预设/创建人。 | 不随 Runtime Event 清理删除；参数预设后续修改/删除不改写已创建 Task。 |
| `task_shops` | Task 的有序 Shop 快照，复合 PK `(task_id,shop_id)`。 | 随 Task 历史保留；当前 Shop 授权变化不改写既有 Task。 |
| `task_assets` | Task 图片关系和位置，复合 PK `(task_id,asset_id)`。 | 随 Task 历史保留；被关系引用的 Asset 不可删除。 |
| `task_events` | Task 运行事件，PK `event_id`，FK Task。 | 默认保留 90 天；只清 Terminal Task Event，不删除 Task/结果/安全摘要。 |
| `schedules` | 定时计划，PK `schedule_id`，FK Team/Device/预设/创建人。 | `deleted_at` 软归档；归档计划不触发，ScheduleRun/Task 历史保留。 |
| `schedule_shops` | Schedule Shop 集合，复合 PK `(schedule_id,shop_id)`。 | 计划保存的业务上下文；归档后保留以支撑历史审计。 |
| `schedule_runs` | 每个理论触发时刻，PK `run_id`，FK Schedule/Task。 | 历史审计保留；不等同 Task 状态机。 |

### 资产与 AI 工作台

| 表 | 用途、主键与关联 | 当前/历史状态与删除、保留规则 |
| --- | --- | --- |
| `assets` | 统一媒体元数据，PK `asset_id`，FK Team/创建人。 | 文件本体在 Storage；Service 仅删除未被现存 Task 引用的 Asset，存储删除与元数据同步处理。 |
| `ai_models` | 可用 AI 模型目录，PK `model_id`。 | 配置目录；引用/退役兼容须由模型服务评估，未定义批量清理。 |
| `template_groups` | Team 提示词模板组，PK `template_group_id`，FK Team/创建人。 | 被 Material Binding 引用时阻止删除；不自动解除反向关系。 |
| `prompt_templates` | TemplateGroup 内有序提示词，PK `prompt_template_id`，FK TemplateGroup。 | 组内删除/重排由服务维护；历史 Generation 来源快照不被反向改写。 |
| `product_material_groups` | Team 商品素材组，PK `material_group_id`，FK Team/创建人。 | 删除时清其自身关系行，不删 Asset 本体；业务历史保留策略待定。 |
| `material_group_assets` | MaterialGroup–Asset 关系，复合 PK `(material_group_id,asset_id)`。 | 仅关系生命周期；解除关系不删除 Asset。 |
| `material_group_template_bindings` | MaterialGroup–TemplateGroup 模式绑定，复合 PK `(material_group_id,template_group_id)`。 | 仅关系生命周期；TemplateGroup 被引用时先显式解除/阻止删除。 |
| `generation_jobs` | AI 生成请求聚合，PK `generation_job_id`，FK Team/模型/创建人。 | 生成历史；当前批量保留/清理规则待定。 |
| `generation_items` | GenerationJob 单项，PK `generation_item_id`，FK Job、来源与输出 Asset。 | 生成历史；Provider retry 不复制 Item，历史保留规则待定。 |
| `generation_item_assets` | GenerationItem 输入 Asset 关系，复合 PK `(generation_item_id,input_role,position)`。 | 随 Item 历史保留；关联 Asset 不可被无检查删除。 |
| `generation_provider_executions` | 每 Item 当前 Provider 执行，PK/FK `generation_item_id`。 | Retry 复用同一行并递增 attempt；不是 Provider 全量历史表。 |

### 经营数据（0039 + 0040 Feature）

| 表 | 用途、主键与关联 | 当前/历史状态与删除、保留规则 |
| --- | --- | --- |
| `shop_operating_daily_metrics` | Shop 每个 Asia/Shanghai 业务日的已确认指标，PK `metric_id`，FK `shop_id`，唯一 `(shop_id,business_date)`。0040 增加可空 `refund_order_count` 与窄范围 `refund_order_status`，仅记录罗盘 `refund_order_cnt`（“退款订单数〔退款时间〕”，单位单）的观测结果。 | 重采更新同一日事实，不累计；退款字段的 `available / unavailable / not_ready / invalid / unobserved` 区分真实 0、字段缺失、未就绪、结构异常和待一次补观测，不能把未知写成 0；后一次非 available 观测不得清空此前已确认退款值。Shop 停用/移除不删历史；数据保留期限待单独批准。 |
| `operating_data_collection_jobs` | 异步采集请求组，PK `collection_job_id`，可 FK 请求人及其提交时的 Team context。 | 手动/重试 item 在发出平台请求前按该上下文重新授权；只保存范围/状态，不保存 Cookie、签名或原始响应；清理期限待定。 |
| `operating_data_collection_items` | Shop+业务日采集状态，PK `collection_item_id`，FK Job/Shop。 | 部分唯一索引防止 active 重叠、lease 支撑安全恢复；失败/暂停保留安全错误码和耗时，不清空此前成功日事实；清理期限待定。 |

所有表变更均须在同一 Gate 1/Gate 2 中同步：SQLAlchemy Model、Alembic Migration、此数据字典、API/
兼容说明和真实 PostgreSQL 验证。文档中标为“历史兼容”或“待定”的对象不构成删除授权。
