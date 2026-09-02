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

| 表 | 职责 |
|---|---|
| `users` | 最小系统用户身份，供负责人等稳定关系引用 |
| `shops` | 店铺基础事实、平台、启用状态、可选负责人和备注 |
| `devices` | 设备身份、启用状态、可选位置和备注 |
| `shop_device_bindings` | Shop 与 Device 的执行资格多对多关系及启用状态 |

核心 ID 使用统一 UUID；核心表使用带时区的 `created_at`、`updated_at`。`shop_device_bindings` 使用 `(shop_id, device_id)` 复合主键防止重复关系。Binding 只表示执行资格，不表达主设备、备用设备或默认唯一设备；同一个 Shop 可以同时绑定多个 Device。

Migration `20260822_0008_shop_soft_delete` 为 `shops` 增加可空 `deleted_at` 与查询索引。`enabled=false` 只表示业务停用，`deleted_at IS NOT NULL` 才表示从正常业务视图移除；软移除不级联删除 Credential、ShopCredentialBinding、ShopSession、Task 或历史数据，`shop_id` 永不复用。

Shop 平台 V1 机器值仅包含 `douyin`、`pdd`。

## Authentication Domain V1 数据库

Migration `20260819_0002_auth_domain_foundation` 增加：

| 表 | 职责 |
|---|---|
| `platform_credentials` | 平台、统一登录标识、加密 Secret、验证码渠道与启用状态 |
| `shop_credential_bindings` | Credential 与 Shop 的可扩展关系；每 Shop 最多一个启用关系 |
| `shop_sessions` | 每 Shop 当前 Session 元数据、乐观并发版本与加密 payload |

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

Migration 创建一个“默认团队”，并把升级时已经存在的全部 User 各回填一条启用 Membership：
`role_code=member, data_scope=team`。空 users 表同样可以升级。任何旧用户都不会自动获得 ALL。
Team 与 Membership 以 `enabled` 停用，不以 Hard Delete 作为主要生命周期操作。

Phase A 不修改 Shop、Asset、Task、Schedule 或 AI Job 的 Ownership。后续 Team Scoped 业务表的
统一语义是 `team_id=数据归属团队`、`created_by_user_id=创建者`；现有
`Shop.owner_user_id` 仍只表示负责人，不承担权限边界。

## Access Management V1 数据库

Migration `20260902_0025_access_management_v1` 增加
`membership_module_accesses`，以 `(membership_id, module_code)` 复合主键保存一条 Team
Membership 可访问的正式 PC 模块。它通过 `RESTRICT` 外键依附 `team_memberships`，不新增密码、
Token、角色继承或任意 JSON 权限列。升级时为既有 Membership 回填当前正式模块代码以保持兼容；
不自动改变角色、Data Scope 或授予 `access_admin`。人员、Team、Membership 均维持启停模型，
不通过本期 Migration 增加 Hard Delete。
