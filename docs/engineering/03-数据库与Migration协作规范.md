# 数据库与 Migration 协作规范

## 1. 基本原则

PostgreSQL 结构演进只能通过 SQLAlchemy Model 与 Alembic Migration 完成，禁止手改任意正式环境的表结构。业务 Feature 对其 Migration 的设计、实现、测试、文档和回滚负责；Integrator 负责 Slot 协调、Gate 2 验证和拒绝不合格候选，不代替 Feature 编写新的数据库变更。

数据库按角色严格隔离：Feature 使用可重建的临时/Feature DB，Integration 只使用 `control_center_integration`，Main smoke 只使用 `control_center_dev`，未来生产必须独立。连接串、密码、密钥和数据导出不得提交。

Feature DB 的生命周期由 Integrator 负责：仅 Integrator 可通过数据库管理员身份创建和删除 Feature DB，并在工程登记表中记录实际分配。Feature Agent 不拥有 `CREATEDB` 权限，且不得自行创建、删除或改用 `control_center_dev`、`control_center_integration`；Feature Worktree 只能使用本地忽略的连接配置访问其已分配的 Feature DB。

分配顺序固定为：Feature 提出需求，Integrator 确认登记与 Migration Slot，数据库管理员创建空 Feature DB 并将 Owner 指向既有最小权限应用角色，Feature Worktree 配置本地忽略的连接后执行 `alembic upgrade head`，才可开始数据库开发。Feature 进入 Green `dev` 后，如该库已无保留价值，仍由 Integrator 删除；不得由 Feature Agent 处理回收。

## 2. Migration Slot

同一时刻只有一个活跃的 Migration Slot。需要结构变更的 Feature 在开始前向 Integrator 申请并登记：

| 字段 | 必填内容 |
|---|---|
| Feature / Owner | 分支与负责人 |
| Slot 状态 | `reserved`、`active`、`released` 或 `rejected` |
| 变更摘要 | 实体、字段、关系、索引和兼容性影响 |
| 依赖 | 需要先合入的 Migration 或无 |
| Migration 标识 | Alembic revision / 计划名称 |
| 验证与回滚 | `upgrade`、必要的 `downgrade`、数据保留与回滚说明 |

- Integrator 只分配、调整和释放 Slot；Feature Owner 才能写对应 Migration。
- 未取得 Slot 的 Feature 不得新增或重排 Migration，也不得借用无关 Migration 偷带结构变更。
- 没有结构变化的 Feature 在 Handoff 中显式写“Migration Slot：无”。
- 发生冲突、升级失败、非预期数据影响或验证不充分时，Slot 状态改为 `rejected`，候选退回原 Feature 修复；不得在 `dev` 上直接修补候选。

当前活跃 Migration Slot：

2026-10-14 A最终Candidate f348565的契约/真实闭环及最后候选池原生人工确认已通过，
正常no-ff集成及合并后验证/精确CI继续。0044仍active直至精确Green，0045仍reserved；
随后先核销0044，再按下列已审范围激活0045，不能把B未验代码或0045混入A Release。
Integration已单一0044，A无后续新增Migration。已有v8事实须保留兼容Reader/Schema/历史审计，
禁止对生产downgrade或直接回旧Reader；具体发布与合后结果见A Gate2文档。

以下旧阶段状态为审查历史，不替代当前事实：
2026-10-13 为 A 段分配唯一 Slot。阶段候选4e584cb降级边界曾拒绝并保留返修占位；
77a1d96的实际执行保护及对应修补已独立复核，恢复`active`。这不表示A完整Gate通过；
不清库、不释放给B，不得并行增加第二条迁移链。

| Feature / Owner | Slot 状态 | 变更摘要 | 依赖 | Migration 标识 | 验证与回滚 |
| --- | --- | --- | --- | --- | --- |
| `feat/product-selection-strategies-v1` / 81a1（A） | `active`（阶段修补接受，未完成Gate） | 新增一张Team-owned `product_selection_strategies`，UUID/Team/User/Shop RESTRICT、编辑version CAS、白名单相对条件及hourly/daily定时草稿；`product_selection_runs`追加可空RESTRICT策略关联。保存/启停不触发取数或创建Schedule；既有候选/观察/run保留 | `20261010_0043` | `20261013_0044_product_selection_strategies_v1`，revision `20261013_0044`，down `20261010_0043` | Feature单一0044保留。4e584cb缺目标库保护的历史拒绝保留；77a1d96先在线查询实际库名，仅允许已登记可重建选品Feature，offline/其它库在锁与DDL前拒绝；再保留排他锁/新数据/并发writer保护。ca97独立8无连接迁移探针及62后端定向通过，upgrade函数未变，未在Integration/生产迁移或降级。Owner真实Feature PG109为开发侧合成平台证据；A参数与真实Gate仍待完成，不以此标Green/DEPLOYED。 |

ca97已通过受保护应用连接与只读事务核实复用Feature库：owner/role为
`control_center_dev_user`，单一`20261010_0043`；候选/观察/run/ShopSession均0，
角色没有CREATEDB/CREATEROLE/SUPERUSER，35433受信任隧道已恢复且严格校验主机公钥。
该检查没有迁移、业务写入或平台请求。0042/0043于2026-10-11统一released，已应用文件不可改写；
新增Schema只由Owner在此Slot实现，Integrator不代写Migration，Integration/生产不用于Feature开发。
Owner应用后，ca97再次以只读事务核实该Feature库单一`20261013_0044`、管理角色权限仍关闭；
本工作树代码与Integration保持0043，不以Feature库升级代替集成Migration或Gate验证。

2026-10-13继续A的阶段Integration验证已由ca97使用精确77a1d96归档，正式升级
`control_center_integration`至单一`20261013_0044`；旧候选/观察/run、经营及Session计数保留。
后续仅通过正式API创建专用策略和一个真实受控Run，未写Feature/Main/生产，未降级或修改0042/3。
这是已执行的阶段迁移事实，替代此前“Integration仍0043”的当前状态，历史审查记录保留；
Slot继续active，A未知映射与原生验收未完，不释放Slot或据此宣称Green/DEPLOYED。

2026-10-13后续B技术提案已由ca97审核；基于81a1真实人类turn
`01a13382-b40f-7552-a6a0-a32a6ec092d2`授权，登记下一预留编号。`reserved`不是第二active，
不授权开始B Migration编写、应用或切换集成Schema。A0044完成Gate并进入精确Green后，
ca97先释放0044、同步B依赖基线，再激活0045。0042/3/4字节不变。

| Feature / Owner | Slot 状态 | 变更摘要 | 依赖 | Migration 标识 | 验证与回滚 |
| --- | --- | --- | --- | --- | --- |
| `feat/product-selection-server-schedule-v1` / 81a1（B） | `reserved`（非DDL技术准备可继续，禁止写/应用新Migration） | 复用schedules/schedule_runs/product_selection_runs，明确pc/server_selection目标、策略FK、服务端每N小时正整数及daily、SelectionRun回执；target/interval组合CHECK及必要索引。选品全局并发初始3可配置、每请求店铺/每非空策略至多1个running，替换旧running常量唯一约束并同步跨进程领取/lease；持久pending队列不因容量占用变blocked。保留全部旧PC数据，不新增表或第二调度器 | A最终候选必须先完成Gate并进入精确Green；先核销0044再串行激活，down `20261013_0044` | 预留 `20261013_0045_product_selection_server_schedule_v1`，计划revision `20261013_0045` | 2026-10-14直接人类turn `01a137cc-b3ba-7071-b6ef-a0dce0ec03a7`更新范围。首次下一严格整点、连续+N小时跨日不重置，COALESCE ONE；准备/平台I/O在锁外，最终人员/Team/Shop/CAS重验，Run/occurrence/next共同提交，保留reused与去重。100计划仅合成PG，须验证跨进程global/店铺/策略上限、忙店跳过、恢复及PC隔离；少量真实自然到点另验。激活后仅登记Feature应用；有B数据保留兼容Reader/Schema/审计，不回旧A镜像或清历史。降级须精确可重建Feature、无新引用及旧唯一约束可恢复，否则fail closed。 |

2026-10-14 上述B增量只更新reserved范围，不激活0045或执行DDL。A精确候选
`a75fbf9d86a48adfe585d20a8cef8c05cd786f3e`的品牌/策略九列/原位操作已由上述直接人类记录确认，
真实品牌两次正式Run/事实/API证据保留；新候选池宽度与目标分页收尾尚待Owner最终Candidate。
因此A0044仍active，尚无新Green，B只继续非DDL准备，不用已通过子项提前释放Slot。

同日B非DDL合同细节审核接受，仍属于同一reserved 0045：`schedules.local_time`只允许
server_selection/hourly为NULL；组合CHECK显式保持PC once/daily/weekly与server daily非空，
hourly的interval_hours非空且正整数、其它分支明确为空，不能依赖SQL UNKNOWN通过。
现行execution_type仅为API派生，不为此新增数据库列或假Skill/00:00。
准备失败继续只记录既有ScheduleRun，SelectionRead批量按当前权限投影最新安全触发结果，
不得伪造SelectionRun/零结果或返回原始错误；实际尝试时间和理论occurrence分开，
明确与手动/后续成功的优先级、reused canonical及PC隔离。新NULL/类型/引用出现后，
恢复旧NOT NULL/global唯一索引须先满足真实数据前置条件，禁止填假值或清历史绕过。

同日B未来多运行关联边界预审：提交/复用与claim须统一选品决策锁及行锁顺序，
候选/运行两侧均检查有效direct与reused策略集合。两个既有running已占用不同店铺时，
不可为coalesce再引入同策略重叠；允许仅此冲突使用原Run表创建服务器限定的策略隔离pending，
稳定队列键包含既有冻结基键与策略UUID，不含随机值、occurrence或策略版本。已有隔离active
先复用，不因占用解除切换canonical；日期、平台scope、Source hash与旧Run不改，
不新增表/状态/通用队列，不写blocked吞掉待执行发生时刻。具体冻结JSON/Reader由Owner
在B正式契约实现并通过PG交错/去重/恢复验证；此设计批准不是Gate、容量3实测或0045激活。

B非DDL候选f4f61c9的技术准备接受与91项无DB定向不改变Slot状态；未新增或应用0045。
OwnerFeature PG90为既有0044上的合成平台测试，不是新Schema验证或Integration Gate。

最近释放记录：

0044阶段审查的降级保护P1已退回Owner修补：目标校验必须在Migration实际执行路径而非仅测试入口，
在LOCK/DDL前在线核对精确登记的`control_center_feat_product_selection`，其它目标及离线删除SQL均拒绝。
该Slot曾rejected返修占位，77a1d96边界经ca97接受后恢复active，但未通过完整业务Gate，仅在Feature应用；修补只加强downgrade，不改upgrade DDL/Head/旧事实，
无需新编号、清库或重建；0042/0043不改。修补实测与新候选仍须ca97独立复核。

| Feature / Owner | Slot 状态 | 变更摘要 | 依赖 | Migration 标识 | 验证与回滚 |
|---|---|---|---|---|---|
| `feat/product-selection-frontend-v1` / 81a1 | `released` | 候选/观察两表、业务专用run与可空last_run_id；无通用队列/Worker/策略调度 | `20260924_0041 → 20261010_0042 → 20261010_0043` | `20261010_0042_product_selection_manual_v1`、`20261010_0043_product_selection_runs_v1`；原已应用文件字节不变 | Gate2 PASS，Integration单一0043，HuanYu正式run10条事实/补充/Real回读成功。Integrator兼容PG81与Owner空Feature专用4项及迁移回滚证据分开记录，见Gate2文档。Feature库retained；正式有run后禁止downgrade/清库，回退需v2兼容Reader并关闭新执行、保留Schema/事实/失败历史。生产升级须由Main Release备份预检后执行，不据此标记已部署。 |
| `feat/operating-data-availability-v1` / 81a1 | `released` | 0041 最小经营起算日审计字段及既有合法零值/未知边界；不推断日期、不改变经营事实 | `20260924_0040_operating_dashboard_refund_orders_v1` | `20260924_0041_operating_data_availability_v1`，revision `20260924_0041` | 2026-10-10 核销历史未同步的 active：已通过 Gate 并进入当前 Green 提交链；管理员只读核实 Integration 和生产均为单一 `20260924_0041`。旧 Availability Feature DB retained，不分配给选品；不重新执行已完成验收或 Migration。 |
| `feat/operating-dashboard-refund-orders-v1` / 81a1 | `released` | 为已证实的抖店 `refund_order_cnt`（页面“退款订单数〔退款时间〕”，单位单）增加最小日事实字段和窄范围观测状态；不含 `refund_order_cnt_pay_time`、商家体验分或通用指标框架 | `20260922_0039_operating_dashboard_data_v1` | `20260924_0040_operating_dashboard_refund_orders_v1` | Gate 2 PASS：Integration 已验证 `0039 → 0040`、完整 Backend 回归、退款定向 PostgreSQL 验证、Frontend 定向测试及 Real build；HuanYu 2026-09-22 在真实平台显式重采后持久化成交额 ¥659.05、成交订单 60、退款订单数 8，Electron Real 看板回读一致；普通更新未再创建任务。Feature DB 与专用 HBA 待 Integrator 回收。 |
| `feat/operating-dashboard-data-v1` / 81a1 | `released` | 新增店铺日经营事实、采集 Job / Item 状态及跨进程防重复约束；生产执行和日调度默认关闭 | `20260920_0038_parameter_preset_historical_reference_deletion_v1` | `20260922_0039_operating_dashboard_data_v1` | Gate 2 PASS：Integration 已验证 `0038 → 0039`、11 项 PostgreSQL 定向测试、完整 Backend/Frontend 回归、一次 HuanYu 真实单店采集、正式查询及 Electron Real 看板人工验收；`control_center_feat_operating_dashboard_data` 与专用 HBA 已回收。本 Migration 的 downgrade 会删除经营日事实与采集状态，只可在可重建 Feature / Integration 测试库闭环；生产已有数据后，应用回滚保持 Schema，数据处置另走获批迁移方案。 |
| `feat/parameter-preset-historical-reference-deletion-v1` / 81a1 | `released` | `automation_parameter_presets` 增加 `deleted_at`，以仅覆盖未软删除记录的 `(team_id, app_id, name)` 部分唯一索引替代全量名称唯一约束；历史 Task 与软删除 Schedule 引用保留，只有未软删除 Schedule（包括 disabled）阻止删除 | `20260919_0037_super_account_team_authorization_v1` | `20260920_0038_parameter_preset_historical_reference_deletion_v1` | Gate 2 Retry 已在 `control_center_integration` 验证 `0037 → 0038`、历史引用/同名重建/Team 范围与既有超级账号场景；后端 455 个非集成测试、参数预设 PostgreSQL 3 个测试及前端 lint/typecheck/475 单测/Real production build 通过。Feature DB 回收待处理，不再占用 Slot |
| `feat/super-account-team-authorization-v1` / 81a1 | `released` | 增加 `users.is_super_account`、Team 级模块/设备/店铺授权关系，以及 Active Member 约束与生命周期支持；不得静默扩大现有成员授权 | `20260912_0036_automation_parameter_schema_snapshot_v1` | `20260919_0037_super_account_team_authorization_v1` | Feature DB 已完成 `0036 → 0037 → 0036 → 0037`。Gate 2 已在 Integration Electron 验证超级账号、A/B Team、共享/独占资源、保存回读、隔离与撤权；生产预检发现的多 Active Team 用户和成员授权集合差异仍必须逐项形成可审查归一方案，禁止默认回填、权限并集或按账号名称推断超级账号。 |
| `hotfix/automation-parameter-schema-snapshot-v1` / 81a1 | `released` | `automation_parameter_presets` 增加不可变 `input_schema_snapshot` JSONB；旧预设仅复制当前 Schema 可识别且已持久化的公共/店铺键，未知键和值保持可诊断 | `20260912_0035_ai_generation_output_compression_v1` | `20260912_0036_automation_parameter_schema_snapshot_v1` | 已进入 Green `dev` 并发布；Integration 与生产均为唯一 `0036` Head。Feature DB `control_center_feat_automation_parameter_schema_snapshot` 仍保留待 Integrator 回收，但不再占用 Slot |
| `feat/ai-workbench-input-preview-output-v1` / 0106 | `released` | AI Workbench Input / Preview / Output V1 已合入 Green `dev`；`GenerationJob` 记录不可变的每任务输出压缩策略快照，生成输出保持可追溯且不会回流为后续输入 | `20260911_0034_automation_parameter_presets_v1` | `20260912_0035_ai_generation_output_compression_v1` | Gate 2 已在 `control_center_integration` 验证 `0034 → 0035 → 0034 → 0035`、压缩后最终 Asset、完整 Backend/Frontend 回归及 Real API/Visual 定向测试；`control_center_feat_ai_workbench_input_preview_output` 已由 Integrator 回收，专用 HBA 规则已移除 |
| `feat/automation-parameter-presets-v1` | `released` | Automation Parameter Presets V1 已合入 Green `dev`；影刀应用参数预设、店铺覆盖、Task 不可变快照及 Schedule 触发时重物化 | `20260911_0033_pc_schedule_date_recurrence_v1` | `20260911_0034_automation_parameter_presets_v1` | Gate 2 已在 `control_center_integration` 验证 `0033 → 0034 → 0033 → 0034`、完整 Backend 回归、参数预设 PostgreSQL 集成、前端生产构建与 Worker 参数桥接；Feature DB 回收待处理（`control_center_feat_automation_parameter_presets` 已由获授权管理通道删除，专用 HBA 规则已移除；不表示其余 Feature 环境已全部清理） |
| `feat/pc-schedule-date-recurrence-v1` | `released` | PC Schedule Date Recurrence V1 已合入 Green `dev`；Schedule 支持一次/每日/每周规则与发生日期筛选 | `20260906_0032_ai_workbench_real_api_v1` | `20260911_0033_pc_schedule_date_recurrence_v1` | Gate 2 已在 `control_center_integration` 验证 `0032 → 0033`、完整 Backend/Frontend 回归；Feature DB 的 `0033 → 0032 → 0033` 与 once/weekly 数据 fail-closed 降级已通过，待数据库管理员回收 |
| `feat/ai-workbench-real-api-v1` | `released` | AI Workbench Real API V1 已合入 Green `dev`；正式工作台改用 Model Catalog、Generation / Template / Material / Asset API，不在 Production 回退 Visual Mock | `20260906_0031_ai_model_management_v1` | `20260906_0032_ai_workbench_real_api_v1` | Gate 2 已在 `control_center_integration` 验证 `0031 → 0032 → 0031 → 0032`，并完成一次真实 Normal Generation；`control_center_feat_ai_workbench_real_api` 已由 Integrator 回收 |
| `feat/ai-model-management-v1` | `released` | AI Model Management V1 已合入 Green `dev`；全局最小模型目录、唯一且启用的默认模型，以及 `access_admin` 管理与 `ai-workbench` enabled Catalog 读取边界 | `20260905_0030_ai_provider_v1` | `20260906_0031_ai_model_management_v1` | Gate 2 已在 `control_center_integration` 验证 `0030 → 0031`；`control_center_feat_ai_model_management` 已由 Integrator 回收 |
| `feat/ai-provider-v1` | `released` | AI Provider V1 已合入 Green `dev`；ToAPIs / `gpt-image-2` 的 External Task Reference 在 Create 前持久化 Durable Intent，未知 Create Outcome fail closed | `20260905_0029_device_task_human_access_v1` | `20260905_0030_ai_provider_v1` | Gate 2 Retry 已在 `control_center_integration` 验证 `0029 → 0030 → 0029 → 0030`，含真实 Normal Generation；`control_center_feat_ai_provider` 已由 Integrator 回收 |
| `feat/device-task-human-access-v1` | `released` | Device / Schedule / Task Human Access V1 已合入 Green `dev` | `20260904_0028_logging_audit_v1` | `20260905_0029_device_task_human_access_v1` | Gate 2 已在 `control_center_integration` 验证 `0028 → 0029 → 0028 → 0029`，并验证单 Team 历史数据动态回填；`control_center_feat_device_task_human_access` 已由 Integrator 回收 |
| `feat/logging-audit-v1` | `released` | Logging & Audit V1 已合入 Green `dev`；重试修复将缺失的审计 `details` 规范化为 JSON 对象 | `20260903_0027_ai_generation_execution_v1` | `20260904_0028_logging_audit_v1` | Gate 2 Retry 已在 `control_center_integration` 验证 `0027 → 0028`；`control_center_feat_audit` 已由 Integrator 回收 |
| `feat/ai-generation-execution-v1` | `released` | AI Generation Execution V1 已合入 Green `dev` | `20260903_0026_ai_workbench_backend_foundation_v1` | `20260903_0027_ai_generation_execution_v1` | Gate 2 已在 `control_center_integration` 验证 `0026 → 0027 → 0026 → 0027`；`control_center_feat_ai_generation` 已由 Integrator 回收 |
| `feat/ai-backend-foundation-v1` | `released` | AI Workbench Backend Foundation V1 已合入 Green `dev` | `20260902_0025_access_management_v1` | `20260903_0026_ai_workbench_backend_foundation_v1` | Gate 2 已在 `control_center_integration` 验证并升级至 `20260903_0026`；空的 `control_center_feat_ai_backend` 已由 Integrator 回收 |
| `feat/access-management-v1` | `released` | Access Management V1 已合入 Green `dev` | `20260901_0024` | `20260902_0025_access_management_v1` | Gate 2 已在 `control_center_integration` 验证并升级至 `20260902_0025`；空的 `control_center_feat_access` 已由 Integrator 回收 |

## 3. Feature Gate 1

Feature Owner 在自己的可重建数据库中完成：

1. 确认变更是属性、实体还是关系，并遵守稳定 ID、约束与索引规则；
2. 编写 Model、Alembic Migration、相应 Repository/Service/Contract 与必要文档；
3. 从干净基线执行 `alembic upgrade head`，验证真实业务读写；
4. 需要降级闭环时，在可重建环境执行 `head → previous → head`，并检查应保留的数据；
5. 在 Handoff 中附上 revision、Slot、数据库角色、命令、结果、影响和回滚方式。

不得以 SQLite 代替 PostgreSQL 报告 Migration 通过，不得在测试后保留无法解释的临时表或数据。

## 4. Integration Gate 2

Integration 只在 `control_center_integration` 验证候选。Integrator 至少检查：

- Slot 已登记且 Migration 序列与当前 Green `dev` 兼容；
- `alembic upgrade head`、关键接口/服务验证和对应自动测试通过；
- 如 Handoff 声明可降级，则在可重建的 Integration 数据库按声明验证；
- 没有把环境文件、数据导出、密码、临时脚本、日志或 artifact 带入 Git；
- 合并后再次运行必要验证，确认 `dev` 保持 Green。

候选失败时先拒绝并保留证据。已合入共享 `dev` 后出现破坏性失败，使用可审查的 `git revert` 回退合并；数据库处理必须根据该 Migration 的明确回滚方案进行，禁止用 Git `reset` 或手改生产/共享数据库掩盖问题。

## 5. Main smoke 与发布

`control_center_dev` 只服务 Main smoke，不是 Feature 或 Integration 的公共试验库。Release Gate 必须确认 Green `dev` 的 Migration 序列、部署顺序、兼容性和回滚说明；生产执行由独立发布流程授权，本规范不授权将开发 Migration 直接用于生产。
