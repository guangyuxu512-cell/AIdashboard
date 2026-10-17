# 商品数据首版开发资源交接

ca97 已接受7d55的最小四表范围，正式分配唯一 active Migration Slot、专用 Feature 数据库和运行端口。精确HBA调整获人类批准后，管理员已完成连接验证及受限配置交付；ca97独立核查通过，资源阻塞已解除。Owner已进入真实Feature PG阶段，不再等待同一许可。

## 授权与基线

直接人类授权来自规划 turn `01a14788-0c80-7b73-be1a-36ad46a23793` 的“那就分配啊”及相邻首版采集入库、查询开发范围。只推进基础手动链路，不授权生产写入、上线、执行清理或新的平台试请求。

Owner：7d55，原工作树 `C:\Users\Administrator\.codex\worktrees\7d55\中控台`，分支 `feat/shop-product-data-real-v1`。从已核 Green `08176d9c5cdbea50114eb0656975a209205761bd` 正常接续并 no-ff 合入原 UI `af6b737281c16e469fdc6300f80cdfb40cb5c981`，初始接续为 `7805ab847976bc5f49e56b49b5e66f362edb49f5`，后续已正常同步最终Green bef7093。旧 UI、样本、共享依赖和历史均保留，不使用 ca97 未成 Green 的治理 HEAD。

申请为 Owner 本地 `docs/_drafts/shop-product-data-real-v1-schema-request-20261017.md`，审核时 SHA256 为 `C377F15DF51A9106E76042AFDBF2226801F1B8C7F1F51803E19FA0877A7EEE13`。本交接中的约束要求优先于草稿未修订处，不由 Integrator 代写业务代码。

## 已分配资源

| 资源 | 登记与状态 |
| --- | --- |
| Feature DB | `control_center_feat_shop_product_data`，Owner 为 `control_center_dev_user`；交付时为空，Owner已从46升级至单一47 |
| 应用角色 | Admin已核 superuser、createdb、createrole、replication、bypassrls均false、memberships0；不轮换凭据、不扩大既有权限 |
| 受保护连接 | 初次HBA拒绝后获精确许可，一次目标只读验证成功。Owner ignored配置已交付，ca97独立核目标、Admin/SYSTEM ACL及4执行开关false |
| Backend | Owner `127.0.0.1:8102`，分配时无监听；不得漂移到 Integration/Main/81a1 端口 |
| Frontend | Owner 原 `127.0.0.1:4177 --strictPort`；分配时无监听，不启动第二 Electron |
| Migration Slot | 唯一 active：文件 `20261017_0047_shop_product_data_v1.py`，revision `20261017_0047`，down `20261015_0046` |

35433 复用已登记的严格 SSH 隧道。该 PostgreSQL 集群也承载其他数据库，隔离边界是精确新 Feature 数据库，不是独立实例。DBAdmin只建新库并按后续精确许可新增该库的访问规则，不改角色、密码、旧规则或其他数据库权限。所有迁移和测试在执行前必须核 `current_database()` 精确等于本次登记名，不接受仅核端口或数据库名前缀。保留旧 Feature、Integration、Main smoke、生产数据及凭据。没有新 Signer、RPA、Worker 或调度服务资源。

Main于北京时间2026-10-17 09:59:18的初次应用连接被明确拒绝，安全原因 `HBA_EXPLICIT_REJECT`，不是密码错误推测。人类在规划 turn `01a14799-18f5-7282-9d93-997c37d7d9cd` 明确“可以。继续。”后，仅新增精确新库/角色/来源的SCRAM规则，旧规则逐字保留，HBA解析0错误、备份可校验，reload不重启。授权后一次应用只读连接验证库名、角色和权限通过，原拒绝历史保留。

管理员正式回执为 `D:/中控台/.dev-runtime/shop-product-data-resource-20261017/db-ready-receipt.json`。ca97随后只在内存解析已登记的 `BACKEND_DATABASE_URL`，独立核完整库名、最小角色、127.0.0.1:35433、禁继承且仅Admin/SYSTEM的ACL、Git ignored/not tracked及4项自动执行开关显式false，未输出秘密、追加数据库连接或操作HBA。资源可用不等于Feature Gate或平台闭环完成。

## 接受的 Schema 与必须落实的约束

四表分别为 `shop_product_data_products`、`shop_product_data_series`、`shop_product_data_generations`、`shop_product_data_metric_snapshots`。稳定商品键唯一 `(shop_id, platform, platform_product_id)`；字符串平台 ID 不转 Number。序列键包含版本化白名单维度但不含商品、分页或当日起止日期；每代保存冻结的精确日期、时区和切片 hash。

快照复合主键 `(generation_id, shop_product_id)`，17 项原值用精确 NUMERIC，unit/state 为固定17键结构，不存任意原始响应。商品、序列、代和快照用同Shop/同序列复合外键保护，均 RESTRICT；current/previous 不能指向别的序列或相同代。显式 NULL 分支 CHECK、非负计数和单调序号须有 PostgreSQL 回归。

**幂等修正是实施要求：**申请中的 `(requested_team_id, requested_by_user_id, submission_key)` 若 Team 可空，普通 UNIQUE 无法保护无团队超级账号。改用非空 `(requested_by_user_id, submission_key)` 唯一，并在回放前复核请求的 Team、Shop、冻结切片和权限；同键不同请求拒绝。不得通过给超级账号造 Team 解决。相同 active 切片跨团队冲突返回安全忙态，不泄露另一团队的回执 ID、发起人或进度。

提交/领取/finalize 复用现有短事务和持久租约模式。平台 I/O 不在数据库事务内；发布时检查有效 fence、全页完整行集合及单调 sequence，同一短事务更新成功代与 current/previous。失败或迟到代保留已有成功数据，不把未知填0或混用旧代补洞，不加Shop全局锁。

事实读取复用当前正式模块与 Shop 授权；运行回执最窄为当前有效上下文内本人发起且仍有目标权限，超级账号使用既有后端校验。SQL 先限定授权和冻结发布代，再筛选、稳定排序、同集合 total 与分页；默认20，前端翻页/刷新不触发平台。

## 首版范围与实现顺序

首版只实现已有业务样本的基准 `sale_type=1/content_type=1`，近1/7/30对应 `date_type=20/21/23`，请求窗口明确冻结。其他枚举、全部45组合、自定义日期、分组权限、自动每日执行和历史删除均隔离，不静默替换选择，不据文件标签推算未知编码。

复用正式 SessionAccessor、DouyinApiClient 和隔离签名链路，增加端点显式精确数字解码而非第二套 HTTP Client。标题/图片固定路径已有两份历史响应20行观察；原值、合法0、未知、单位未确认分开。金额unit3和比率unit4尚无官方同商品同窗换算证据，原值精度照存，未核定展示/区间筛选保持不可用，不借经营分制或Mock百分比推算。

Owner 现在可完成固定路径解析、合成测试、DTO/Service/Repository及前端窄 Adapter；收到连接后先核目标库，再正式 `alembic upgrade head` 至既有46，随后按 active Slot 实施47、约束/并发/权限/发布回滚的真实 PostgreSQL 测试。正式请求、全页采集及 Integration 真实闭环必须另有指定店铺/窗口/预算授权，开发测试不能冒充平台成功。

当前/上一成功代的读取引用可以实现，历史代和失败摘要暂保留，不执行删除或TTL。新增表升级兼容旧业务；应用回滚保Schema/事实/审计并关新入口。降级只准已登记精确可重建 Feature 库，在线目标核验且四表全部无业务记录；其他库或任一新记录均拒绝，不改0042–0046。

## 下一责任与产物

DBAdmin资源交付已完成。7d55已正常同步Green bef7093，完成事务原子发布、权限查询、HTTP及typed Real接线，交付精确Candidate `5915009d85be2ea912d8498dc0807b141938f399`；Gate1回报947项后端、45项真实Feature PG及856项前端通过，库仍为单一47。此前80/118项离线与12项Schema PG是阶段证据，不代替完整闭环。

ca97已独立精确归档源审、87项商品后端、78项共享回归、83项商品前端、lint/type和Real构建通过，chunk hash与交接一致；细节见本轮Gate2审查记录。Integration PG/API、新的真实平台全页及Real展示仍未覆盖，当前不是总Gate2或Green。新平台预算尚未明确前不执行；不把旧单页或合成数据当真实采集。Integration只写 `control_center_integration`，商品数据仍无生产发布授权；已发布登录提示不含本Feature。

## 经营恢复修复及固定范围诊断

状态：最小修复开发中，固定8项生产只读诊断已完成。人类在规划 turn `01a147d1-9808-7f92-be8d-3e8c750f8752`、message `01a147d1-9881-7c92-a5e9-4c0efeac4717` 明确要求“赶紧修复”，替代此前 `01a147bd` 等商品完成的顺序。81a1从精确Green `bef7093b755cea60fda55bbcc6177b5723d4738a` 正常建立 `feat/operating-data-session-recovery-v1`，ca97负责独立Gate2。商品数据仍由7d55独立推进，不占用其专库、8102/4177和0047；本项优先无Schema修改，不新增迁移槽。

截图为近7天、全部店铺、全部平台，覆盖13/21，提示“部分店铺经营起算日未确认，按完整日期范围统计”。查看缺失列出以下8项，全部显示“采集失败（店铺登录态验证失败）”：

| 店铺 | 日期 | 项数 |
| --- | --- | --- |
| HuanYu | 2026-10-10、2026-10-11 | 2 |
| MyCookLab | 2026-10-10至2026-10-15 | 6 |

Main于北京时间2026-10-17 11:08:57在生产 `fe7ce217dfee8a0bf3374c6da42a902d20ad9e4d`、`control_center_prod`、单一0046完成一次有界只读事务。8日各只有1个历史Item，均为daily/FAILED/retryable，阶段session_preparation、安全码SHOP_SESSION_VALIDATION_FAILED；单Item尝试及失败链累计均3，达到实际上限3。86400秒冷却已过，retry_after为空，原Item为最新项，无活动项；8个`session-restored:{原Item}`键均未使用。8日事实均无记录，不得记为零或仅退款缺失。

两店均启用、平台身份存在、经营起算日为空。HuanYu为valid v3、MyCookLab为valid v2，捕获均晚于原失败；但快照时最近验证距今约33分钟，超过现有300秒新鲜度。VALID标签不等于本次已复核，也不证明当前会话失效。诊断未新增验证、登录、平台请求、采集或业务写入。安全白名单逐项证据在Main本地 `.dev-runtime/operating-recovery-readonly-20261017/production-evidence.json` 及摘要，后续复用，不重复扫描生产。

最小实现复用原单Item retry、跨版本一次性去重和既有队列。读资格与锁内提交共用判断，不扩非DAILY及其他失败白名单。旧默认300秒校验契约保留；只有明确显式操作才可请求先排队复核，原执行器通过既有HealthService实际检查当前保存Session后再取经营数据。失败终态、累计次数、身份/版本、授权撤销、停用与09:00边界保持。排队不是补齐成功，须原任务成功且正式查询更新后才反馈完成。不得伪造验证时间、删除freshness门禁或让用户为此反复登录。

81a1开发资源已就绪。Main于11:19:26通过既有35433和81a1受保护配置作一次全新只读连接，精确确认 `control_center_feat_product_selection`、`control_center_dev_user`、单一20261015_0046；应用角色五项高权均false、memberships0，Owner与public权限符合原登记。除本探针外无连接或活动任务；原users2/teams3/shops2保留，其他核对业务表为0。ca97正式分配复用，不要求重复连接或新建库/HBA。原8101/4176无监听并保留独占，四执行/调度键启动前显式false且核环境覆盖。允许精确库名及角色双重护栏后的定向PG、正式API与替身collector、页面自动化；只清理本次稳定UUID夹具，不准全库truncate。安全回执为Main `.dev-runtime/operating-recovery-readonly-20261017/feature-resource-preflight-result.json`。

不连接Integration/生产代替Feature库，不清旧数据，不借用商品数据库或Slot。当前无Schema修改、不占迁移槽。只复用未受影响的真实身份/窗口证据，本项不新增机械登录/关闭窗口验收；生产平台调用、补采、业务写入和部署仍未授权。

### 历史修订与补采一致性

人类在规划 turn `01a147c0-46f8-7b13-9886-3c90ba5ad5ee` 追加担忧：缺失日后来补采可能遇到退款回算，和较早采集的日期不一致。先以本经营接口的官方口径及现有证据确认各指标业务归属时间，是支付时间、退款发生时间还是原订单时间；与观测/采集时间分开，不借商品数据或其他退款字段定义推算。不把可能的历史修订当成已证明事实，也不把平台合法修订直接判为程序错误或承诺历史值永久不变。

核查必须覆盖四个层次：

1. **防重复。**核同店铺、业务日期、维度的唯一键和实际幂等覆盖/版本发布，检查补采是否重复累加；重放和失败记录不能成为额外事实。
2. **单日原子更新。**核一次成功/失败的事务与发布边界，是否混入同日不同代的成交、退款字段；如允许保留部分旧指标，必须核来源与更新时间如何表明，不能静默当成同次新结果。保留已有成功数据及失败证据。
3. **窗口刷新。**分别比较缺失8项、已采13项及整个固定窗口的采集时间/批次和官方可修订规则。仅补8项不自然保证与其余13项属于同一观察时点；是否需要刷新已采日期，由真实口径与实现证据决定，不预设必须整窗重采。
4. **截止时间可见性。**核跨日、跨店合计是否混用不同采集时点及界面展示的时间含义。平台逐页/逐日请求不天然保证同一时刻快照，不能把一次批次或最后完成时间宣称为整窗绝对同时一致。

核实已有原始指标值、历史/版本、批次与更新时间是否可追溯，保留已有记录，不删除或补造历史；未保留的证据如实列缺口。最终最小方案分别说明上述防重复、单日原子发布、窗口刷新规则和截止时间表达。当前可实施最小修复及隔离自动化测试；任何新生产平台对照、受控重采、事实重写或清理仍不在当前权限内。

交付为Owner精确Candidate/Gate1、ca97独立Gate2及自动化闭环证据，保留已有成功数据与失败审计，区分合法零、未知及未采集。当前授权不含生产重试/补采、建新任务、改状态、清失败、重置次数、改起算日/分母、关闭保护、新平台请求、重复登录或发布。需要生产执行时，须另列精确店铺日期、原因、次数及影响并取得对应授权，不能以开发测试通过宣称8项生产已恢复。
