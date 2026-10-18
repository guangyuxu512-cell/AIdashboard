# 数据库与 Migration 规范

## 商品数据首版四表与 0047

2026-10-17，ca97正式分配唯一active `20261017_0047`，down `20261015_0046`，
Owner7d55/feat/shop-product-data-real-v1，专用 `control_center_feat_shop_product_data`。
已在精确Feature应用至单一47并验证空新表47→46→47保留旧User标记；应用后的47不得改写。
共享PG集群并非独占实例，实际执行前必须
在线核current_database()精确完整库名，不以端口、角色名或feature前缀代替目标核验。

| 新表 | 身份和约束 | 保留及可见性 |
| --- | --- | --- |
| shop_product_data_products | UUID shop_product_id，Shop RESTRICT；唯一(shop_id,platform,字符串platform_product_id)及主键+Shop复合引用目标 | 稳定店内身份，不因某窗口未出现删除，不建立Team所有权 |
| shop_product_data_series | UUID series_id，唯一Shop+rolling_series_hash；期间/维度/契约版本，不含商品或具体当天日期；next/published序号及current/previous同系列FK | 只维护读取引用，不执行TTL；两个引用不可相同，失败不切指针 |
| shop_product_data_generations | UUID generation_id，series+Shop复合RESTRICT、Actor非空/Team可空；唯一(series,sequence)、非空(actor,submission_key)；同Shop具体来源pending/running部分唯一 | 冻结窗口、原生date_type、白名单scope、页与指标覆盖、安全阶段、持久lease；回执按Actor/当前Team/Shop再校验，不能由共享事实泄漏操作上下文 |
| shop_product_data_metric_snapshots | PK(generation,shop_product)；同Shop复合RESTRICT；标题/图片可空，17原值NUMERIC无猜测小数尺度，固定17键unit/state JSONB | 来源是完整已发布代；真实0保留，未知不补0、不用旧代补洞；新代失败不删旧事实 |

原值列为已核17 platformCode，具体清单见26号契约和固定registry。JSONB不能携任意响应或认证；
available值必须非空、有限、非负且unit匹配，计数须整数；invalid可保留有限负原值但不显示为事实0。
逐项状态与unit完整性分开。官方商品列表调用链已核定unit3金额除100为元、unit4为原比例分数；仍不能据全页完整推断逐项有值。原三代回执unit_complete_rows=0保留采集当时语义，当前查询可确认单位不回填旧回执；原值NUMERIC、unit/state和0047均不变。
发布需同短事务验证fence、全页覆盖、同系列和单调序号并更新成功代/两指针；平台IO不跨DB事务。

升级仅新增四表，不改0042–0046。应用回滚保Schema/事实/失败审计并关闭新入口；
0047 downgrade在线精确只允许上述可重建Feature，锁表后发现任一新记录即拒绝，离线删除DDL拒绝。
PG外键、并发、权限、升级/空新表回退必须真实验证，离线DDL编译不能记为PG通过。

## 0046 候选结果及基础补充（当前Feature，未部署）

revision `20261015_0046`，down `20261013_0045`；已在登记Feature应用，42–46均不得改写。
新增 `product_selection_result_items`：UUID item_id主键，execution_run_id→product_selection_runs、
observation_id→product_selection_observations均RESTRICT；unique(execution_run_id,observation_id)。
discovery_scope_hash为规范化相对条件键，discovery_state=new/known/unknown，hit_at为实际命中时间，
snapshot为最小冻结榜单字段；scope/observation/hit及hit/observation索引。只追加真正rank成员，
事实/fence/计数/member同事务；不复制原平台响应或秘密，失败/空榜没有虚构成员。

Candidate追加blocked、blocked_changed_at、blocked_changed_by_user_id→users(RESTRICT)及可空
discovery_tracking_version；同Team商品全来源共用屏蔽，审计复用audit_logs；旧商品标志不回填。
Observation追加basic_info_status JSONB和非负basic_info_version；状态/逐字段成功时间独立于旧值，
NULL/missing/invalid或请求失败不清空成功事实。Run追加闭式operation_kind(rank/basic_info)、
target_observation_id→Observation(RESTRICT)、可空result_detail_version和basic target/created/id索引。
basic无strategy、saved_count=0，独立单项补充CHECK；同原队列/容量/Shop锁/租约，非第二状态系统。

旧NULL detail_version=未记录，不反推完整空。rank事实与不可变批次职责分开；基础补充不改rank计数/成员。
无批准保留期不自动删除。停用Shop历史可授权读取/屏蔽，补充执行仍拒绝；删除及Team引用继续RESTRICT。
应用回退保留兼容Reader/Schema/数据；降级仅精确Feature加锁后没有任何新语义，包括非NULL明细版本、
basic Run、基础状态/版本、屏蔽及其审计，即使零成员也拒绝。实际迁移/关系验证详见本Feature Gate1。

## 20261013_0045 服务端选品调度（B实施中）

ca97已串行释放0044并激活0045/down0044，Owner仅在已登记Feature库实施；未完成B Gate或自然触发验收。
不新增表，不改已应用42/43/44，不在迁移中创建策略计划或删除历史。下面旧running常量说明为0043历史。

| 表 | 0045新增属性/关系/约束 | 职责与保留 |
| --- | --- | --- |
| schedules | target_kind(pc默认/server_selection)、可空selection_strategy_id RESTRICT FK、可空正整数interval_hours；server的device/skill/preset必须NULL，input={}，仅上海hourly/daily；hourly local_time必须NULL且interval非空正数，其他类型local_time非空、interval必须NULL。每策略未归档计划partial unique | PC原once/daily/weekly字段、关联及事实保留；选品条件来自策略，不伪造设备或Skill。停用不删计划/历史，归档不再触发 |
| schedule_runs | 可空selection_run_id RESTRICT FK到正式选品提交回执；task_created只关联Task，selection_run只关联选品回执，blocked两者空；原unique(schedule_id,scheduled_for)不变 | 理论到点与实际created_at分别保存；无候选/准备失败仍有触发审计，不建立第二执行状态机。保留期限未定，不清理 |
| product_selection_runs | 原global running常量unique替换为request_shop_id running部分唯一和非空strategy_id running部分唯一；原活动条件唯一/提交唯一/lease/source关联保留 | 全局容量由同一选品事务决策锁+数据库count/claim跨进程保证，完整direct/reused策略集合避免重叠；busy保持pending。默认容量3在正式配置/领取路径接通后才生效 |

Team/User/Shop授权仍由正式Service及SQL可见域执行；Schedule/策略及ScheduleRun/回执一致性在短事务复检。
0045升级在线加锁预检旧PC组合，发现异常拒绝而不改数据。降级仅在线精确Feature库、锁后没有server/hourly/
selection引用/多running/新隔离元数据时允许；真实使用后保留B兼容Reader/Schema关闭新执行，不能降级清历史。

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
| `shops`                | 店铺基础事实、平台、启用状态、可选负责人、备注及可选经营覆盖边界 |
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

## 当前完整表清单（Feature 0043 阶段候选）

2026-10-13 A策略Feature的实际introspection为单一 `20261013_0044`、**48**张表（含Alembic）；
下方47表是0043历史基线，本段只新增 `product_selection_strategies`，未删旧表。
新增/变化登记如下：ca97已在Integration正式升级0044并保留旧数据/Session，生产仍0043。
0044已共享应用，不再改写；实时v4只扩JSON契约，不改Schema，不能把Feature结果写成已发布。

| 表 | 用途、主键与关联 | 状态与保留 |
| --- | --- | --- |
| `product_selection_strategies` | PK UUID strategy_id，Team/User/请求Shop外键均RESTRICT；name、正version CAS、enabled、严格相对条件JSONB与单份hourly/daily计划草稿JSONB；Team/updated/ID和Shop/ID索引 | A保存配置，不创建Schedule或取数；未有删除功能或批准保留期，不自动清理。Team仅剩策略仍不能删除。普通成员当前Team/Shop SQL授权先于分页/总数和直接ID。 |
| `product_selection_runs`（0044追加） | 可空 `strategy_id → product_selection_strategies.strategy_id` RESTRICT及策略/created/ID索引；v3条件JSON内保存提交时策略ID/version和冻结日期，不回填历史关联 | canonical和reused回执分别保存自己的关联；复用不改canonical或复制计数。改策略/启停不改旧run；最近结果沿各自回执解析并过滤历史Shop当前权限。 |

0044降级本身先在线读取`current_database()`，只允许已登记可重建目标
`control_center_feat_product_selection`，不是任意`control_center_feat_*`前缀；离线降级拒绝输出删除DDL。
非授权目标在LOCK/DDL之前拒绝；授权目标再加排他锁，发现任何策略或非空run关联即fail closed。
只在该Feature空新实体时允许0044→0043→0044，保留0042事实/0043旧run；正式应用回滚
保留新Schema/数据并使用兼容Reader。2026-10-13阶段审查P1修补仅加降级执行保护，
0044的upgrade DDL/revision/down_revision及已应用Feature结构不变，无需清库或重建，不改0042/0043。
v1/v2原解析/fingerprint保持；v3有界官方排名分页及原bool首次上榜筛选。仅首次上榜筛选启用时，
来源context为v2并显式first_listed_only=true，hash含该口径，与原不限筛选来源分开；原v1 hash不变。
2026-10-13实时扩展不改表：run JSON版本4单日冻结、strategy JSON仍相对版本1，
source date_selection以shanghai_realtime_today与7日策略区分，无备用日期。旧JSON/hash不变；
实际v4写入后应用回滚必须保留支持v4的最终Reader/0044/事实，不能直接换77等旧Backend或降级清库。

以下清单已与独立 Feature DB `control_center_feat_product_selection` 在 `20261010_0043` Head 的实际 PostgreSQL
introspection 核对（2026-10-10）：共 **47** 张表，含 Alembic 元数据表。0042增加候选/观察两表，0043只追加业务run及观察last_run_id；不改写已应用迁移或复制会话。该结构尚未进入Integration/生产，不代表真实选品闭环已接通。未有已批准
保留期的表明确标为“待定”，文档整理本身不授权删除、改名或迁移任何历史数据。

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
| `shops` | 店铺主档，PK `shop_id`，可关联 `owner_user_id`。0041 增加可空 `operating_start_date`、来源、设置人和设置时间；设置人 FK `users.user_id` 为 `RESTRICT`。 | `deleted_at` 软移除且 `shop_id` 不复用；停用/移除不删凭证、Session、Task 或经营历史。经营起算日仅由有管理权限人员显式确认，来源当前为 `manual`；不得从中控台接入、首次采集或首次出单推断。起算日与全部审计列要么同时为 NULL、要么同时存在；若已有更早已确认成交/订单/退款事实，拒绝设置会隐藏事实的较晚日期。 |
| `platform_credentials` | 加密平台凭证，PK `credential_id`。 | 独立于 Shop；绑定停用/解除不自动清除凭证，敏感数据处置规则待单独定义。 |
| `shop_credential_bindings` | Shop–Credential 关系，复合 PK `(shop_id,credential_id)`。 | 启停/解绑不级联删任一事实；当前每 Shop 最多一个启用关系。 |
| `shop_sessions` | 每 Shop 当前加密 Session 与版本，PK `session_id`，FK Shop/来源 Device；唯一 Shop 和既有租约也承载首次已有店登录的 NOT_CONFIGURED 保留行。 | 保留行不是可用会话，API不展示内部占位时间，Accessor拒绝解密；匹配权威验证成功才以租约+版本CAS替换。失败保留原事实，软移除 Shop 后保留，不能导出明文 Cookie。 |
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

### 经营数据（0039 + 0040 + 0041 Feature）

| 表 | 用途、主键与关联 | 当前/历史状态与删除、保留规则 |
| --- | --- | --- |
| `shop_operating_daily_metrics` | Shop 每个 Asia/Shanghai 业务日的已确认指标，PK `metric_id`，FK `shop_id`，唯一 `(shop_id,business_date)`。0040 增加可空 `refund_order_count` 与窄范围 `refund_order_status`，仅记录罗盘 `refund_order_cnt`（“退款订单数〔退款时间〕”，单位单）的观测结果。 | 重采更新同一日事实，不累计；退款字段的 `available / unavailable / not_ready / invalid / unobserved` 区分真实 0、字段缺失、未就绪、结构异常和待一次补观测，不能把未知写成 0；后一次非 available 观测不得清空此前已确认退款值。0041 的起算日不会删除、更改或伪造该表的事实；Shop 停用/移除不删历史；数据保留期限待单独批准。 |
| `operating_data_collection_jobs` | 异步采集请求组，PK `collection_job_id`，可 FK 请求人及其提交时的 Team context。 | 手动/重试 item 在发出平台请求前按该上下文重新授权；只保存范围/状态，不保存 Cookie、签名或原始响应。全范围早于已确认经营起算日时普通更新不创建空 Job；清理期限待定。 |
| `operating_data_collection_items` | Shop+业务日采集状态，PK `collection_item_id`，FK Job/Shop。 | 部分唯一索引防止 active 重叠、lease 支撑安全恢复；失败/暂停保留安全错误码和耗时，不清空此前成功日事实。核心固定路径只有 `unit`、无标量值时以 `DOUYIN_OPERATING_DATA_METRICS_UNAVAILABLE` 终态记录，不写日事实、不代表 0 或未经营、也不自动重试；直接缺失或显式 null 的核心指标分别使用同一 `unknown` 展示语义的窄范围安全码。0041 会把尚未发起、且早于已确认起算日的 item 标为 `SHOP_NOT_OPERATING_ON_DATE` / `skipped`，不调用平台；清理期限待定。 |

### 罗盘手动选品事实与运行（0042 + 0043 Feature）

2026-10-11有限日期回退复用0043的JSONB，不改变表结构/Migration Head。request_conditions v2包含原始条件、上海接受日、冻结主备scope和独立date_outcome；唯一活动fingerprint排除可变outcome，v1原哈希保持兼容。observation的source_context.date_selection附安全计划/实际窗口，source_scope_hash仍只由实际请求scope生成。outcome与事实更新均经过现有租约fence和数据库时钟；不同窗口不混写。含v2记录后不可回退到只识别v1的旧应用，应用恢复保留Schema/数据并使用兼容版本，不能清库或改写已应用0042/0043。

| 表 | 用途、主键与关联 | 当前/历史状态与删除、保留规则 |
| --- | --- | --- |
| `product_selection_candidates` | Team-owned源商品身份，PK `candidate_id`；FK `team_id → teams`、`created_by_user_id → users`，全部RESTRICT。`platform_product_id` 为字符串，唯一 `(team_id,platform,platform_product_id)`；Team/稳定ID查询索引。 | 当前仅douyin候选，不是正式商品库。重复获取复用身份；Shop会话不复制，不同Team候选归属不混合。保留期待定，不自动清理。 |
| `product_selection_observations` | PK `observation_id`；RESTRICT FK候选及 `request_shop_id → shops`。唯一 `(candidate_id,request_shop_id,source_scope_hash)`；Shop/检查时间及候选/检查时间索引。明确日期/白名单来源条件、实际商品商家、排名、四项原始区间、补充类目/上架日期、NUMERIC差评率原值及原unit、安全错误摘要分别保存。 | 当前来源成功事实，不充当队列。相同/旧榜单执行和其迟到补充受版本条件限制；失败/缺失保留已确认值及有效取数时间。`basic_info_retrieved_at` 仅表示最近完整补充；部分/失败另记尝试时间和安全码。当前授权过滤先于最新来源选择、排序分页；停用/移除/撤权不物理删除历史。保留期待定，不自动清理。 |
| `product_selection_runs` | UUID PK run_id；RESTRICT FK Team/User/请求Shop及可空自外键reused_run_id。唯一Team/User/submission_key；canonical活动Team/Shop/规范条件部分唯一、running常量唯一、pending及Team/created索引。JSONB仅版本化白名单原始/冻结条件与明确日期；状态、阶段、计数、安全错误、租约独立。 | canonical执行及内部reused回执分开；回执无执行计数/lease/起止时间，不被领取。合法空成功0、取数失败未知null、basic_info失败partial；Team仅剩run仍阻止删除。历史run不是逐商品快照；保留期待定，不自动清理。 |

0043为观察增加可空RESTRICT `last_run_id → product_selection_runs.run_id`；仅写canonical、同Team/Shop且有效lease。当前事实可被后续成功run替代关联，旧run条件/计数保留。不能把旧run当前空关联误解为原执行无结果。

来源hash采用版本化白名单业务参数，不含分页、Cookie、Token、签名、指纹、页面追踪或完整请求URL。
JSONB只承载固定来源/商家/指标结构，不保存整份平台响应。不同期间/请求店铺不互相覆盖；商品商家平台ID
不能当成中控台请求Shop UUID。差评率unit=4的显示尺度未确认，不在查询层擅自转百分比或用来筛选。

独立Feature已验证 `0041 → 0042 → 0041 → 0042`，原表记录保留、新两表无测试残留。downgrade删除新
选品事实，只允许在可重建测试库使用；正式数据出现后应用回退保留Schema/事实，不自动降级。
0043运行契约已由ca97审核；独立Feature验证0043→0042→0043保留0042事实，有run回退拒绝。只在run为空的可重建Feature允许该回退；正式/共享数据保留Schema。运行服务、正式平台适配及应用执行入口已接线，但映射未冻结时只允许过期lease恢复，不领取或请求平台；UI执行未开放，不冒充完整闭环。

所有表变更均须在同一 Gate 1/Gate 2 中同步：SQLAlchemy Model、Alembic Migration、此数据字典、API/
兼容说明和真实 PostgreSQL 验证。文档中标为“历史兼容”或“待定”的对象不构成删除授权。
