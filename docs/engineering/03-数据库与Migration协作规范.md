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

2026-10-17商品数据首版真实接入：已核当前代码最高单一 `20261015_0046`，该槽已 released，
没有后续 active。规划人类 turn `01a14788-0c80-7b73-be1a-36ad46a23793` 已授权首版开发和资源分配。
ca97 审定7d55最小四表申请（原申请SHA256 `C377F15DF51A9106E76042AFDBF2226801F1B8C7F1F51803E19FA0877A7EEE13`），
正式激活下表唯一 Slot。此前“未分配下一Slot”为历史状态，0042至0046字节不改。

| Feature / Owner | Slot 状态 | 变更摘要 | 依赖 | Migration 标识 | 验证与回滚 |
| --- | --- | --- | --- | --- | --- |
| `feat/shop-product-data-real-v1` / 7d55 | `active`（ca97正式分配，仅Feature实施） | 新增稳定店内商品、滚动序列、采集代/回执、17指标快照四表；同Shop/同序列复合FK、有限活动切片唯一、单调序号/lease fence与原子current/previous发布。幂等必须覆盖超级账号无Team：使用非空Actor+submission_key唯一并复核冻结上下文，不能依赖nullable Team复合UNIQUE；未知单位/值保状态、不填0 | 精确Green08176，后续正常同步新Green；down `20261015_0046` | 文件 `20261017_0047_shop_product_data_v1.py`，revision `20261017_0047` | 新独立 `control_center_feat_shop_product_data`，Admin建空库/受保护配置交付并核目标后，Owner升级既有46、实施47并完成真实PG升级/空库降级/约束并发测试。非指定可重建Feature或任一新表已有数据时downgrade拒绝；正式回滚保Schema/事实/审计、关闭新入口。无自动删除/每日采集/真实平台执行授权。 |

Schema与具体资源边界见 `shop-product-data-real-v1-resource-handoff-20261017.md`。Integrator不代写
Model/Migration，不写Feature业务表。空库创建和凭据交付由既有DBAdmin通道执行，不能复用旧库；
建库尚待管理员完成，不将Slot active写成数据库或真实闭环已就绪。

2026-10-16生产核验完成：Main正式Release21229eff经CI38790697624/Deploy38791100315成功，
新鲜pre46备份1039309字节/restore目录344项可读后升级生产单一20261015_0046；
12类旧字段逐行摘要及计划/Session/审计全保持，0046文件不变，Slot继续released/无active。
生产已有新语义后仍禁止downgrade清历史或直接回旧B Reader；保留兼容Reader/Schema及审计。
后续独立死代码清理无Schema/DB/Slot需求，不能借此回收旧事实或改迁移。

2026-10-16正式核销：0046对应完整885已通过Gate1/Gate2、正常no-ff合后复验及精确Green
1773a97d27c56512a620337e3259cceabadca2f1，CI38789232361三Jobsuccess，现released，
暂无active Slot。Feature/Integration单一46及事实保留；生产由Main在新鲜备份和正式Release
中45→46，不据Green冒称生产升级成功。后续纯治理HEAD不是新Green，不自动分配下一Slot。

2026-10-16更新：完整885b618的Gate2A/2B及人类发布授权已核销；0046已应用文件、
Integration事实及可读pre46备份完整保留。当前Slot仍active至正常no-ff集成及精确dev CI Green，
届时正式released，不提前分配下一Slot。生产仍按Main新鲜Release检查从45升级46；
已有策略/Run/PC/经营事实和审计须保留，不复制集成夹具，不降级或按旧零数据假设处理。
下表bfaae14/真实basic未完为旧阶段，当前证据见候选池Gate2最终确认节。

2026-10-15新资源：B45已released，实际版本文件/登记最高45，无其它active；规划人类批准
候选池独立Feature及单项基础补充后，Owner最小方案经ca97审查接受，现串行分配唯一active如下。
retained Feature库已新鲜只读核单一45/八项业务0/无其它连接/最小角色，复用而不清库；
Owner正常建分支并同步本次治理后才可编写/应用新46，不改42–45、不用Integration/生产开发。

| Feature / Owner | Slot 状态 | 变更摘要 | 依赖 | Migration 标识 | 验证与回滚 |
| --- | --- | --- | --- | --- | --- |
| `feat/product-selection-candidate-result-filters-v1` / 81a1 | `released`（完整885b618 Gate1/2及精确Green1773a97，CI38789232361三Jobsuccess） | Candidate Team级屏蔽/审计；1张append-only canonical结果关联及明细版本；关闭式rank/basic_info Run与Observation最小字段状态/fence，复用原Executor/容量/lease，不新建队列/扫描器 | 基线Green9bb64ac，down单一`20261013_0045` | `20261015_0046_product_selection_candidate_result_filters_v1`，revision `20261015_0046` | Feature/Integration单一46；可读pre46备份、正式升级及12表旧字段保留通过；正式API/合成场景与59394f85真实basic成功及原生确认分别记录。文件SHA256 F87B00229065BADC506CE3BE38E59AB9E7B2DF1833918941D8F4833F924C2F9C，42–45不改。新明细标志即使0items、新basic/状态/屏蔽审计存在均拒绝丢语义；downgrade仅精确可重建Feature，共享/生产保Reader/Schema/审计并关入口。生产升级/健康/旧数据另由Main Release核验，不据Green预标DEPLOYED。 |

新增紧凑列表共享任务`feat/compact-product-list-foundation-v1`为纯前端依赖，Migration Slot：无，
不连接DB、不创建库或DDL。81a1原Feature及Integration已应用0046完整保留，不因从Green45代码
建立共享分支而运行旧迁移/Backend、降级或重建已有46库。7d55只消费将来获批纯前端共享SHA，
不得通过merge整条选品Feature偷带0046模型/迁移。0046仍只归上表原业务Feature，真实basic未完成前不释放。

2026-10-15最终B：0045已released，当前无active Slot。精确Green9bb经Release Gate正常Main382，
main CI38599163540/正式Deploy38599686878 attempt1 success；生产经新鲜pre45受保护备份981523字节/
restore list340项可读后正式升级单一`20261013_0045`，Main11表旧字段摘要及ca97只读SHA/Head/计数核验通过。
只启用持久B定时配置并正常重载Backend，实际并发3；原PC/A/经营/Session保留，生产选品0/未复制夹具。
Feature/Integration45与实际1.0.6/Profile保持；有B数据后保留兼容Reader/Schema/审计，不回旧A或downgrade。
下表B当前结果已核销，其余active/reserved或旧生产43/44为已保留阶段历史；未分配下一Slot。

2026-10-15最新：B Gate1/Gate2/直接人类原生确认及正常no-ff合后验证全部通过；精确Green
`9bb64ac76bf9e0f51fb1715517cf8c18cef63e22`/CI38597874343三项success已核实并推送。
现正式核销`20261013_0045_product_selection_server_schedule_v1`为released，无active Slot。
Feature/Integration已单一0045、生产此时仍0044；Main受权在Release Gate/新鲜备份可读后正式升级。
原Slot表active为已保留历史，不覆盖本项核销；未分配下一Slot、不开发其它Feature或释放旧数据。

2026-10-15 B精确7db已完成Gate 2及直接人类原生确认、获得继续合并/CI/发布授权。
0045仍唯一active至精确dev CI Green核销，Feature/Integration单一0045及旧事实保留；
本次不改已应用迁移。生产当前A103b1c80/0044，0045由Main在Release Gate、备份可读后正式升级，
不把Gate或集成样本当成生产部署。下面旧“尚待原生”等为已保留阶段历史。

2026-10-14 人类授权的`feat/production-buildx-builder-selection-v1`是纯发布工程返修，
Owner81a1、ca97 Gate2、Main Release；无数据库/Schema/Migration需求、不占槽，
不改42/43/44/45，不连接旧B Feature45实施业务持久化。0045仍唯一active，A/B发布边界不变。

2026-10-14 B当前事实补记：完整7db6578技术审查接受后，ca97使用受保护Integration备份、
正式Alembic从精确归档升级`control_center_integration`0044→单一0045，原业务/PC/Session保留。
已应用42/43/44/45字节不改，不降级或清历史；仅专用正式API配置及有限自然timer验收。
0045继续唯一active，B Gate2未完成/未合dev，不能因Integration迁移或Feature合成测试标released。
下文“Integration未应用45”保留为之前阶段，不覆盖本次实际升级。A与工程修复已正式部署，
生产实际103b1c80/单一`20261013_0044`；Main备份restore list330通过后正式升级，
ca97独立只读复核SHA/Head/服务及09:00原配置。未包含B45、未写新生产策略/Run；
B验收与发布独立，细节见`product-selection-server-schedule-v1-gate2-20261014.md`。

以下为Owner提交时的初始Slot历史，已被上述当前状态及下方完整Gate登记替代：

2026-10-14 ca97正式确认A精确Green `f5d4866459acf3e29459a9920c03c1e9118a8839`、
CI38503895984成功，已交Main Release。0044已串行released；唯一active为
`20261013_0045_product_selection_server_schedule_v1`，revision0045/down0044，Owner81a1。
允许在已登记Feature库实施批准的Schedule/Run目标、hourly interval与显式NULL组合CHECK、
FK/partial unique、运行名额索引及共用队列；不新增表，不修改已应用42/43/44。
当前数据库仍0044，尚未应用0045或完成B验收；降级须精确可重建Feature在线校验和无新残留，
不清理既有事实或伪造PC字段。下方旧active/reserved为历史，不覆盖此次正式通知。

| Feature / Owner | Slot 状态 | 变更摘要 | 依赖 | Migration 标识 | 验证与回滚 |
| --- | --- | --- | --- | --- | --- |
| `feat/product-selection-server-schedule-v1` / 81a1（B） | `active`（ca97正式批准） | 复用schedules/schedule_runs/selection_runs，server目标与策略/回执RESTRICT FK；hourly正整数间隔、nullable local_time明确组合；每店/策略running partial与共享领取全局容量 | `20261013_0044` | `20261013_0045_product_selection_server_schedule_v1`，revision `20261013_0045` | 仅Feature实施/PG验证；旧PC及A事实保留，完整Gate/自然到期证据未完成。生产应用恢复保留兼容B Reader/Schema，禁用server路径而不降级清历史。 |

历史阶段记录：

2026-10-14 A最终Candidate f348565的契约/真实闭环及最后候选池原生人工确认已通过，
正常no-ff精确Green `f5d4866459acf3e29459a9920c03c1e9118a8839` 已合后复验及CI通过，
CI https://github.com/guangyuxu512-cell/AIdashboard/actions/runs/38503895984 三项success。
现先核销0044为released，再按下列已审范围串行激活0045；唯一active为B，不混入A Release。
Owner须正常merge精确A Green，再在登记Feature库编写/应用0045及完成Gate1；治理登记不是Green。
Integration已单一0044，A无后续新增Migration。已有v8事实须保留兼容Reader/Schema/历史审计，
禁止对生产downgrade或直接回旧Reader；具体发布与合后结果见A Gate2文档。

以下旧阶段状态为审查历史，不替代当前事实：
2026-10-13 为 A 段分配唯一 Slot。阶段候选4e584cb降级边界曾拒绝并保留返修占位；
77a1d96的实际执行保护及对应修补已独立复核，恢复`active`。这不表示A完整Gate通过；
不清库、不释放给B，不得并行增加第二条迁移链。

ca97随后已明确B后续revision `20261013_0045`（down `20261013_0044`）为reserved，
仅预留编号及审核最小Schema/事务提案，不授权写或应用DDL。唯一active仍A0044；
A完整Gate与精确Green后由ca97串行释放0044、激活0045。Owner B分支当前只有非DDL准备，
不把预留状态当数据库结构已实现，不修改0042/0043/0044。

| Feature / Owner | Slot 状态 | 变更摘要 | 依赖 | Migration 标识 | 验证与回滚 |
| --- | --- | --- | --- | --- | --- |
| `feat/product-selection-strategies-v1` / 81a1（A） | `released`（Gate2/Green及2026-10-14正式部署完成） | 一张Team-owned策略表、version CAS、相对条件与定时草稿，runs可空RESTRICT策略关联；保存/启停不取数或创建Schedule，旧事实保留 | `20261010_0043` | `20261013_0044_product_selection_strategies_v1`，revision `20261013_0044`，down `20261010_0043` | A验证期Feature/Integration0044证据保留，现B隔离45；最终Green af57/CI38547082755、Main103/CI38549554911及Deploy38550018844 attempt2 success。Main受保护新dump/restore list330后正式生产升级单一0044，ca97只读复核；新策略/Run/平台请求0。77实际降级guard保留；生产已有v8或策略后必须保留兼容Reader/Schema/事实/审计，不downgrade或旧Reader回退清数据。 |

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
| `feat/product-selection-server-schedule-v1` / 81a1（B） | `released`（精确Green9bb及正式生产382收口） | 复用schedules/schedule_runs/product_selection_runs，pc/server_selection目标、策略FK、每N正整数/daily、回执/组合CHECK/索引；全局3可配置、同店/有效策略至多1，持久pending容量等待及lease，旧PC保留；不新增表或扫描器 | 正常merge精确A Green `f5d4866459acf3e29459a9920c03c1e9118a8839`，down `20261013_0044` | `20261013_0045_product_selection_server_schedule_v1`，revision `20261013_0045` | 7db Gate1/Feature合成PG、ca97正式Integration升级与真实自然执行（一次客户端完全退出）/原生确认/合后复验/精确CI全通过；Main备份可读后正式生产45，11表旧字段保留/ca97只读复核。42/43/44/45字节不改；有B数据保留兼容Reader/Schema/审计，不回旧A或降级清历史。downgrade仅精确可重建Feature/锁后无B引用、旧非空与唯一可恢复，否则拒绝；生产单一45，服务/持久开关核验通过。 |

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

2026-10-14 B激活后的首Feature升级记录：SQLSTATE42704，旧计划表实际约束存在命名约定
双前缀，短名称不存在；事务完整回滚，Head0044和数据未变。0045曾rejected保留B返修占位，
Owner仅修正尚未应用0045的已知短/双前缀精确预检及op.f命名，不改旧迁移或手改表/权限。
正常upgrade成功后，ca97独立只读核实已分配`control_center_feat_product_selection`单一
`20261013_0045`；候选/观察/run/策略/ShopSession/计划/回执/Task八项均0，应用角色仍最小权限。
现核销返修并恢复0045 active。该资源/Schema接受不是B完整Gate：数据存在时的迁移/约束、
并发领取、服务端自然到点、状态投影和PC隔离仍须Owner继续PG/定向验证；Integration与生产未升45。
已应用45按既有规则保留，后续差异先交Integrator审核，不改写42/43/44或直接修正式库。

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
