# 罗盘选品策略 A / 服务端定时 B 契约

## 2026-10-18 品牌标签映射纠正

最新官方页面确认覆盖了 2026-10-14 的标签方向：`all → "-1"`、`known → "1"`、
`unknown → "0"`。此前同条件 `0`/`1` 两次只读请求只能证明两种筛选结果不同，不能自行证明
哪个标签对应哪个值；旧段落保留为历史失误记录，不再作为新请求契约。

新接受的非默认品牌请求使用 v9，并在手动、策略定时、主备窗口和最终 Query 中使用同一正确映射。
历史 v7 和含旧品牌条件的 v8 仍以当时实际发送的 `known=0`、`unknown=1` 解析；不改旧 JSON、
fingerprint、来源事实或审计。新 submission 因版本和实际参数不同，不复用旧活动执行；旧
`submission_key` 重放仍返回其原冻结请求。无 Schema/Migration 变化。恢复版本必须继续读取
v1–v9；若需停止新写，使用既有开关并保留数据，不降级到旧 Reader、不清库、不改历史记录。

## 交付边界与基线

2026-10-13 人类直接任务；Owner 81a1，Integrator ca97，Release Main。A 分支
`feat/product-selection-strategies-v1` 从精确 Green `3128d6ad1048dfda1240148e863ea0c98eb6247f`
创建，与已发布 `0102dd6d051f89907bad113c35310bbab69412ec` 业务树一致。
保留原 StrategyList / StrategyDrawer、五项体验修复及可用店铺登录，不重新设计页面。
本文件是本轮新增契约，历史“策略保存未接入”仅为旧阶段记录，不表示本轮完成。

A：已确认条件转换、策略保存/读取/编辑/启停和原界面 Real 绑定。
B：A 验收后另交候选，扩展现有 Schedule/到期扫描/时间规则至服务端选品。
两段分别 Gate 1 → Gate 2 → Green/CI → Main Release，Owner 不合 dev/main、不发布。

## 复用

| 现有能力 | 本次用途 | 调整边界 |
| --- | --- | --- |
| product_selection 的 run/service/executor/repository | 手动和之后的定时共用冻结条件、去重、租约、事实和结果 | 不造第二执行器/通用队列 |
| SessionAccessor、DouyinApiClient、Connector、Signer | 真实类目/榜单/basic_info | 仍签实际发送的 Cookie，日期改变重新签名 |
| SelectionCategoryService / Cache | 授权店铺实际树，24小时缓存与显式刷新 | 命中缓存前后授权；不能用行业7替换用户选择 |
| StrategyList/Drawer、Query、ShopSelector、CategorySelector | 原工具栏、列表及右侧条件抽屉 | 不用执行结果页替换策略管理 |
| AppRadio/Select/Switch/Input/NumberInput/TimePicker/Button | 相对日期、品牌/价格、计划草稿、保存与启停 | 四主题 Token/尺寸不变，无新基础控件 |
| ScheduleService / Repository / time_rules / due scanner | B 的 hourly/daily 和防重复触发 | PC once/daily/weekly 与设备/Worker链路保留 |

## A 最小持久化（0044，ca97已审核登记）

`product_selection_strategies`：UUID strategy_id；Team、创建人和请求自有 Shop 外键 RESTRICT；
name、递增 version、enabled；版本化且严格白名单的相对条件 JSONB；唯一整策略定时配置
（scheduled/hourly或daily/上海HH:mm）JSONB；created_at/updated_at。
相对条件不存固化日期、Session、原始响应或 URL；商品商家不是请求自有店铺。
`product_selection_runs.strategy_id` 可空 RESTRICT；原运行和事实保留、不回填猜测关联。
没有删除功能或自动保留期，保留期未定。

API 使用既有 product-selection 模块、Human Actor 和当前 Shop 授权；普通成员先 SQL
Team/Shop 过滤再搜索/分页。写入重验有效 Team/启用且未删除抖店。
新建策略及未关联策略的手动提交仍要求明确的当前业务Team，不推测默认团队。
已有策略直接ID的GET/PUT/启停及关联手动提交：后台重新验证当前人员的super权限后，
由已保存strategy.team_id确定有效团队；不要求切换全局Team，不修改原归属。
普通成员仍按当前模块/团队/店铺授权SQL过滤，不能套用super资源上下文。
类目I/O后再次从原人员及资源重验；已撤super/Shop授权、失效Team或CAS冲突均拒绝。
Team 仅剩策略也阻止物理删除，不能让新表产生未解释的级联数据丢失。

关闭策略（enabled=false）只要求当前Actor/Team/Shop可见授权和版本CAS，不要求该店铺
执行就绪，也不读取Session或请求平台。重新开启仍要求所关联店铺启用、未删除且为抖店；
实际执行继续独立复核资格和Session。新建/完整保存校验本次提交的目标店铺，仍拒绝停用目标。
编辑旧停用目标换到另一已授权启用抖店允许；原配置的访问权限/CAS仍校验，不能借新目标绕过旧配置撤权。
仅在旧停用目标上改名称的完整PUT仍明确拒绝，应使用关闭PATCH或选择合法新目标，不泛用旧目标执行校验。

- GET `/api/v1/product-selection/strategies`：分页/名称查询，批量附最近真实执行摘要；
  无结果就是 null，不伪造一次运行。关联回执解析到其 canonical 执行。
  默认稳定排序为created_at DESC、strategy_id ASC；启停/编辑仍更新真实updated_at，但不把它
  当行序键。授权/搜索先于排序和分页；同创建时刻由ID稳定排序，不增加排序配置页面。
  前端按正式保存/启停响应原位更新既有Query行，再读取正式列表；已有编辑保持当前页/筛选/滚动，
  新建回第一页按新增规则展示。改名后若不再命中筛选，服从正式过滤，不强行保留已排除行。
- GET `/strategies/{strategy_id}`：已保存相对条件、计划草稿、version 和 enabled。
- POST `/strategies`：保存配置，不请求平台、不提交 run、不启用调度。
- PUT `/strategies/{strategy_id}`：完整编辑＋expected_version；CAS冲突保留客户端草稿。
- PATCH `/strategies/{strategy_id}/enabled`：expected_version＋enabled，同一授权/版本边界。
- POST `/runs`：增加可空 strategy_id；执行当前提交条件，不读取策略覆盖草稿，不顺带保存。
  已保存策略须同Team/Shop可写；未保存草稿保持无策略关联。相同submission_key重放
  同时检查条件和策略关联，不能跨策略挪用回执。不同key的相同活动条件仍复用已有执行。

POST关联策略时须同时提供strategy_id和strategy_version（正整数）；服务端锁定同Team/Shop
当前策略并核对版本，保存v3（7d）/v4（实时）/v5（1d、30d）/v6（双边价格）、历史v7/v8
或新v9（纠正后的非默认品牌）request_conditions.strategy快照。后续编辑不改任何旧run。
不同策略复用活动条件时，canonical身份/版本不改；每个reused回执保存自己的策略快照，
提交响应的strategy表示调用者快照，execution表示canonical计数/状态/冻结条件。
按回执ID GET仍沿旧契约解析canonical；策略列表按各自提交回执批量取canonical最近结果，
并再次按历史请求Shop的当前授权过滤，换Shop后撤销旧Shop不能泄露旧run。

精确`GET /runs/{run_id}`的进度读取同样遵守资源上下文：后台重新核验为super后，
按已保存Run的Team重新校验有效人员/Team/模块再读取，不要求切换全局Team。
canonical可能是被关联策略复用的旧无strategy执行，因此不能只看canonical.strategy_id。
回执仍校验与canonical同Team/Shop/指纹，普通成员仍按Team/Shop授权读取；失效super不能沿用旧标记。
资源Team重新解析后，必须以该次权威Actor再走精确Run可见查询；不能把首次super取得的行
直接交给DTO。若校验期间super被撤回，正常Team/Shop SQL边界仍生效，未授权则404。
`GET /runs`列表继续采用当前Team筛选，精确ID例外不改变列表总数、归属或任何事实。

升级期仍在执行的旧v2默认条件可与新v3提交共享任务，但必须Team/Shop、全部原始条件、
排名/页范围及冻结的两段日期完全一致，保留旧canonical/指纹；新回执记录自己的v3策略快照。
相同submission_key跨日先重放原请求；新key次日不能因相对周期相同就复用昨日窗口。

A 的定时字段真实持久化，但 `schedule_available=false`，next_run_at=null；界面明确尚未调度。
保存/启用不偷偷取数。百应/达人配置保留布局但不可执行，不丢掉用户条件后假成功。

`BACKEND_PRODUCT_SELECTION_STRATEGY_MANAGEMENT_ENABLED=true` 默认开放策略配置写入，不开放平台
自动执行。false时capabilities.strategy_save_available=false，POST/PUT/启停PATCH拒绝，
GET/列表/运行/事实继续读取；前端保留列表与已保存配置，只禁新建/保存/启停。
平台执行仍独立由既有 `BACKEND_PRODUCT_SELECTION_EXECUTION_ENABLED` 控制，默认false。

## 平台证据与待补项

| 条件 | 当前可靠依据 | 本轮处理 |
| --- | --- | --- |
| 短视频 | 已成功路径及 rank_data_type=1 | 不外推商品卡/百应 |
| 近7天 | date_type=21；上海冻结主备7日及一次回退已有批准 | 保留原规则和首查阶段边界 |
| 实时 | 用户旧Query明确实时date_type=1；2026-10-13 08:12:39+08 ca97同条件当前日服务器HTTP200/st整数0/10条/total200，Integration stored v6正式链路 | 接受时上海当天begin=end=00:00:00，独立v4单窗口，无7d回退；只证明该时刻首10条，不称全天可用 |
| 近1天/近30天 | 官方控件yesterday=20/thirty=23及ca97同条件服务器单因素各一次HTTP200/st整数0/10条；同商品区间随周期变化 | 上海接受日D冻结1d=[D-1,D-1]、30d=[D-30,D-1]，type20/23；新v5单窗口，不扩7d备用 |
| 行业/类目 | 当前授权cate_list完整包装树；ca97正式会话只读行业5/非零父路径HTTP200/st整数0/10条，结合原行业7多层Query确认结构规则 | 包装根ID作为industry_id，根下实际有序非零路径逗号连接为category_id；动态读取所有返回根，不按5/7/10/14建白名单。行业根全部表达尚未确认，仍不可执行 |
| 品牌 | 最新官方页面确认知名1/非知名0；ca97同Session/冻结条件各一次服务器HTTP200/st整数0/10条、两集合不同；不限-1保持 | 新选择/保存/回显/实际请求使用all→"-1"、known→"1"、unknown→"0"；旧v7/v8保留历史实际值，不以商品响应brand_type推断 |
| 价格 | 默认不限及ca97固定日期下20-100、仅上界改20-40的服务器单因素成功及商品集合变化 | 双边元数规范连接为price_bin；单边未知拒绝，原SKU价带不裁剪，详见v6 |
| 首次上榜 | product_info.newly_on_ranking 为平台布尔标记 | 按该返回标记筛选，不以本地first_seen代替；未知不当false |
| 排名 | product_info.rank 官方原值，page_result总200已有证据 | 有界分页，按官方排名1–200筛选，不用本地行号 |

平台最少补验由ca97使用环境合法Session协调。Feature只用合成响应；不索取Cookie/cURL，
不重复旧成功试验、不将 HTTP200 或模拟数据算成新业务成功。

### 授权整树的通用行业/父级转换

类目GET/24小时缓存已有完整`nodes`与默认`industry_id`。包装树由顶层存在默认行业ID的
根识别，scalar只表示当前默认选择，不能作为整树行业白名单；前端逐根派生各自industry
scope，后端按所选ID匹配实际根，再逐层检验category路径，行业根不能混入category_id。
旧unwrapped树保持其scalar行业及原有序路径兼容，不猜未知树类型。
非零父类目“全部”仍选实际父路径，UI`/*`只用于显示，选择时去掉；平台0节点/合成ID不发送。
行业根自身未确认空/省略/0表达，保持无requestScope及公开DTO至少一个category ID的边界。
当前Shop匹配/授权/启停、缓存命中前后鉴权、切店清理和保存回显规则不变；缓存不按行业拆分。
ca97只读结构依据不是本新候选正式保存/执行入库或原生证据，新候选仍须相应Gate2最小闭环。

### 实时v4冻结与可读性

复用原run JSON与执行器，v4仅用于已确认实时：date_plan只有accepted_local_date，
scope.date_type=1、begin=end为该上海日00:00:00；无backup_scope。仅可选择primary后写事实。
合法成功空榜单直接成功0；621000704、签名/HTTP/其他失败原样分类，不走7d补查。
相同submission_key跨日先重放原日，不读类目或重发；新key新日不复用旧日活动。
来源date_selection.policy=shanghai_realtime_today，backup日期/理由为null，页面显示实时及实际当日。
旧v1/v2/v3格式/hash、7d source context及受限回退保留；策略相对配置version仍1。
无新表/列/Migration。实际平台证明来自ca97一次只读请求，非该v4候选入库/原生验收；
v4尚需当前候选端到端验证，不重复旧7d认证或为单条basic_info失败加盲重试。

## A 已实现范围的最小Integration验收清单

ca97在精确候选Real Integration自行准备，Owner不写该库/配置、不另开Electron。
先核验Backend/Renderer实际代码树及Integration唯一Head、保留既有人员登录/ShopSession与事实。
表中检查是待执行清单，不是已有真实Integration/Electron结果；未知参数补证和B不阻塞纯CRUD。

### 夹具与计数边界

- 优先用现有有product-selection模块权限、已明确选Team的人员与该Team授权的HuanYu店铺。
  从正式`GET /categories?shop_id=...`取实际树，采用行业7及树中真实ordered非0父级路径。
  既有Query样本是依据，不把其历史固定日期或类目硬写成用户当前选择。
- 测试策略统一`stage-2a1-selection-strategy-<短后缀>`，记录新strategy_id/version和相关run/receipt_id。
  初始enabled=false、scheduled=false；随后专门验证计划草稿保存，保持schedule_available=false和next_run_at=null。
- 纯CRUD可在手动执行开关关闭时验；准备/打开抽屉可读取类目，先完成树加载再计数。
  HTTP检查/GET列表/类目API不等于榜单取数。POST/PUT/PATCH本身应零新增Run、零rank/basic_info/ShopSession读取。
- 不停用真实HuanYu、不撤销真实人员权限、不破坏合法Session。负向使用专用合成Team/人员/Shop/授权，
  可复用Owner `selection_context`和`_api_client`的模型/数据关系，但由Integrator按既有正式服务/隔离测试创建。
  用真实UUID、不复用浏览器拦截的`strategy-shop`等假ID；普通API校验不注入super或绕模块/Team guard。
- 没有DELETE策略API，不编造清理接口；纯测试Rows是否由稳定ID夹具清理按Integrator授权处理。
  真实运行/候选/来源/失败审计及仍被引用的策略保留，勿按名称模糊删除；不降级Integration库验0044。

### API → 数据库 → 同一Real页面

| 检查 | 正式入口和最小步骤 | 必须看到的结果 |
| --- | --- | --- |
| 保存不执行 | POST `/strategies`，相对7d/不限品牌价格/实际行业7路径/完整排名，enabled=false | 201，version=1；名称/Shop/条件/计划入库，无绝对日期、Run/Schedule或平台请求 |
| 列表/读取/刷新 | GET `/strategies?page=1&page_size=...&search=...`、GET `/{strategy_id}`；刷新页面/重新进入或已有正常登录后读取 | 原保存值与API/DB一致，按当前授权先过滤再total/分页；不加载Mock，不生成新任务 |
| 编辑保存 | 原列表“编辑”，改名称及已支持条件，PUT `/{id}`＋expected_version | 同一ID、version+1；重开抽屉回显新值，未新建另一个策略，不取数 |
| CAS/草稿保护 | 两次读取同版本，第一次合法PUT后，第二次仍用旧expected_version；页面失败后取消再重开 | 409/PRODUCT_SELECTION_STRATEGY_VERSION_CONFLICT；未覆盖保存值，失败时抽屉/草稿保留，不自动重试或提交Run |
| 启停 | PATCH `/{id}/enabled`＋当前expected_version，开/关及重读 | version单调递增、仅配置变化；A的每小时/每日只为草稿，不显示已调度/虚构下次时刻 |
| 失效目标修正 | 合成Shop先启用保存，随后停用；关闭PATCH，再尝试开启；另编辑换合法新Shop | 关闭200且零ShopSession/Run；开启409；合法换新Shop200；完整PUT仍拒绝提交停用新目标 |
| 权限边界 | 专用夹具跨Team、撤Shop授权、错ID，包含关闭false分支；有模块权限人员无Team写 | 不得越权读取/修改/关停；CAS仍检查。无Team写拒绝，不自动选择Team；原Shop历史事实保留 |
| 独立立即获取 | 已保存策略中改未保存条件后POST `/runs`，附strategy_id/version；未保存草稿不附关联 | 保存配置未改变、不自动创建策略；当前提交条件在Run冻结，最近结果关联正确，状态可轮询 |
| 只刷新结果 | GET `/runs/{receipt_id}`、列表/候选/详情，页面刷新与重进 | 仅读数据库，零再提交/平台请求；失败不作为成功空榜单，未知不填0，候选basic_info部分失败不清空有效事实 |

### 必要真实执行及证据边界

在同一真实树条件下由ca97协调最小排名范围执行，选择能与官方rank/first标记对照的样本；
不要因技术测试通过重复认证、换Cookie或为边界拉满200项。第一页probe/实际total/官方rank过滤保持原逻辑，
需验21名以后的情况时按最小所需页数，首次上榜按官方bool而非本地首次见到。
若first筛选结果恰为空，如实记录而非强行回退找商品；反例/大边界继续合成验证。
记录条件（相对周期与实际类目）→冻结首备/实际采用日期→strategy版本/run/receipt→候选/来源→API→Real页面，
以及刷新不重发、必要同条件重复提交不重复建档。保留窗口普通/最大化与已确认布局/数字格式/缓存。
行业根全部仍待准确编码；品牌标签及已确认双边价格按本轮证据实现，
不等待全部证据，不把本清单或浏览器正式API拦截测试当原生/真实平台Gate。

## B 预定扩展边界（未实现）

同一 Schedule 底座明确区分 PC 与 server_selection，设备必填仅适用于PC；选品关联策略，
到期调用正式选品服务创建run，不生成虚假Task或Device。新增hourly＝上海整点，daily＝用户上海时间。
用既有unique(schedule_id,scheduled_for)、短事务claim、COALESCE ONE恢复；同策略活动轮次不重叠。
PC读取API在服务端排除选品记录，不靠前端隐藏。迁移待A完成后另申请登记。

## 迁移与验收

ca97已登记唯一Slot `20261013_0044_product_selection_strategies_v1`，
revision `20261013_0044`，down `20261010_0043`。Feature已应用并验证迁移闭环，
ca97现已在Integration正式升级0044且保留旧数据/Session，生产仍0043；0044也已进入共享环境，
本次不改Migration文件或Schema，禁止改写0042/0043/0044或通过降级清库绕过记录保留。
阶段审查4e584cb因P1/P2退回，Slot已由ca97改为rejected返修占位，未释放编号/库；
随后77a1d96精确返修独立边界接受，由ca97恢复active，仅允许A继续，不是全A Gate；B不能抢新Slot。
已分配Feature库 `control_center_feat_product_selection`，角色 `control_center_dev_user`；
8101/4176 strictPort，35433受信任隧道由ca97恢复。实际Feature为单一0044，
47业务表＋alembic_version（public共48表），末次ShopSession/策略/run均0；
应用角色无CREATEDB/CREATEROLE/SUPERUSER，不复制生产凭据。
升级保留旧候选/观察/run；降级仅可重建库且无新策略/关联run时允许，否则fail closed。
正式应用回滚保留Schema/策略/事实/失败记录，用兼容Reader关闭新写/新执行，不清库。

阶段审查P1修补：0044的实际downgrade执行路径在任何LOCK/DDL前读取`SELECT current_database()`，
精确允许已登记的`control_center_feat_product_selection`，拒绝Main/Integration/生产、
其它未授权Feature及无法确认的目标；不信任URL配置或测试包装器。offline模式拒绝生成删除DDL。
之后仍保留锁后查数据/并发writer的原保护。0044尚为未通过Gate的Feature返修迁移，
此次仅修降级安全边界，不改upgrade DDL/revision/down_revision或已有事实，不要求Feature清库/重建，
该修补发生在当时仅Feature应用0044的阶段；随后Integration已由ca97升级，生产未应用0044。
旧阶段兼容事实保留，当前不再编辑已进入共享环境的0044，不新增Slot。

兼容回滚使用最终候选（支持历史v7/v8及纠正后v9品牌、v6价格、v5历史单窗口、v4实时run/来源、旧v1/v2/v3及首次上榜来源）的Backend Reader，
写入v4后不能直接换成77a1d96/3128等旧Backend，即使先关闭UI/执行开关也不等于兼容。
将上述两个开关写入既有受保护部署配置并按规范重启，停止新提交/claim；已发网络请求不承诺撤回。
必要时用既有SelectionRunService.recover_expired在租约过期后记录interrupted，保留事实/回执，
不自动重发；旧执行者仍受DB时钟/lease fence保护。可以回退Renderer，但Backend Reader及0044保留。
Feature已验证只读开关和数据保持；真实部署/重启流程仍须ca97/Main Release核验，不作已发布声明。

本轮尚在契约审核/开发，A/B均未完成；独立记录合成、PostgreSQL、真实平台和Electron证据。
真实到点自动执行必须通过B的Integration闭环，手动调用执行器不能替代。

## 2026-10-14 近1天/近30天单窗口v5

已读取ca97受忽略的官方5074脚本枚举及2026-10-13同店stored HuanYu v6的
baseline/day1/day30只读对照。两新增窗口只改date_type和日期，各1请求、0业务写，HTTP200/st int0。
响应无日期echo，同商品3822441844692877383金额端点随1/7/30天变化，结合官方控件确认周期。
1d不是实时1或自然日2；type20、上海D-1单日。30d用type23、D-30至D-1含首尾30完整自然日。
无固定刷新时刻保证，业务拒绝按原安全分层，不将621解释成已知日期未就绪。

v5仅1d/30d和当前已确认其它条件：复用无backup的accepted_local_date锚及scope，
新增存储版本5，不改写旧run/date JSON/hash；策略条件仍相对version1，原executor执行。
选窗只能primary；合法空成功0，621 int/string、签名、HTTP、结构异常不补查、不扩7d回退。
同key跨日先重放旧计划，new key才用新接受日。来源policy为shanghai_1d_yesterday或
shanghai_30d_complete_days，真实begin/end与null备用字段明确展示，刷新只读数据库。
capabilities支持四个原有日期选项，保存/编辑/提交使用同一转换，无新UI或Migration。
写过v5后不能直接回6fc/183旧Backend；回滚保留数据/0044和v5兼容Reader，通过现有
管理/执行开关停止新写/claim，不改JSON或降级清库。只读参数证据不等于新v5候选入库/页面验收。

## 2026-10-14 双边自定义价格v6

ca97使用Integration HuanYu stored v6，在同一冻结7d日期10-06至10-12、行业/路径、第一页10条和
brand=-1下，默认、price_bin=20-100及20-40各一次只读。HTTP200/st整数0/各10条，业务写入0。
初始诊断记录仅标成功、效果未知；后续单因素集合对照已由ca97审核接受：20-100排除默认¥8、¥9–13等，
20-40又排除20-100的¥49–59、¥58–68、¥89–276、¥99等。请求单位元，不转分，不写JSON价格对象。
返回仍有¥39–115、¥21–69多SKU区间；不能据此宣称所有SKU都在条件内，也不在本地再次删掉这些商品。
下界20包含的样本已观察，上界等值/单边/所有组合并未逐一平台实测，报告边界保持明确。

沿现有price_mode/custom与price_above/price_below字段，两个明确、有限、非负的十位以内元数，
至多两位小数，最低<=最高；单边null、逆序、指数/NaN/无限/超精度明确拒绝。
`custom_price_bin`用Decimal无舍入规范化为ASCII `最低-最高`，20.00/100.0为20-100。
`PRODUCT_SELECTION_PRICE_RANGE_INVALID`为422；公开DTO非法格式继续422/VALIDATION_ERROR。
保存相对条件及原始边界，不生成日期/run；编辑回读、手动运行用相同转换。切回不限时两边界不进入提交。
旧字段名是兼容标识，不代表strict大于/小于；Real标签及摘要使用最低/最高价格（元），Mock旧交互保持隔离。
四主题与原控件/布局不变。修正边界后只更新既有价格字段校验反馈，不清除其它错误或关闭草稿。

v6只扩展已有run JSON Reader：保留original双边数、实际scope及冻结计划；旧默认v1–v5格式/hash不变。
复用原日期冻结/执行器，rt/1d/30d仍单窗；7d只在首选第一页合法成功空且未入库时补查冻结备用一次。
自定义价格的621000704（int/string）及其它失败不补查；Service/Reader同时阻止该业务拒绝回退。
两窗口保持同一price_bin，实际采用窗口的business/source hash/日期入库，不混窗；原price_band保留。
失败、basic_info缺项、租约及权限规则不扩展。无Schema/Migration，0042/0043/0044不可改写。
写过v6后必须保留v6兼容Reader，不能直接回0d10旧Backend；回滚用既有开关停新写/claim并保留事实/审计。

本轮Owner仅Feature合成PG与正式API拦截验证；上述参数只读证据不是新v6候选的真实入库/原生验收。
ca97须在精确候选加载后补最小条件→run→事实→API→同一Real Electron证据；若当前验收授权仅配置/只读，
保持真实入库未验，不绕过范围。未知品牌/行业根全部仍关闭。
B0045仅reserved，尚无到点服务端执行；A整体验收/Green/发布及B仍PARTIAL，不混入完成声明。

## 2026-10-14 品牌接通与策略列表容器适配

本节记录2026-10-14当时采用、后于2026-10-18被纠正的方向：知名brand_type=0、
非知名=1、不限=-1。新请求不得继续使用该方向。
结合ca97 stored HuanYu v6同日冻结7d、同Shop/类目/价格/第一页的0/1各一次只读：HTTP200、st int0、
各10条且商品集合不相同。不能仅用HTTP200判断，亦不能因两组商品响应brand_type皆0改掉页面标签映射。
标签证据和服务器效果证据分别登记，不重复索取Query/Cookie/cURL，不硬编码样本日期/路径/动态参数。

相对策略条件version1不变，品牌仍是all/known/unknown；历史v7 Reader保留本节旧方向，
新BRAND_TYPES按顶部2026-10-18纠正执行，均不使用truthy默认值。capabilities与原AppSelect接线，
保存/编辑回显/手动提交共用现有服务。默认v1–v6 JSON/hash不变，实际主备、分页、source与API保持品牌。
日期/价格校验复用既有规则；非默认brand近7天仅首选合法成功空且未入库可补冻结备用一次，
621和其它失败不扩大补查；rt/1d/30d仍单窗。拒绝非法品牌、主备品牌漂移及其它请求条件篡改。
原HTTP/Session/Signer、Team/Shop授权、basic_info及first-listed/rank逻辑不改，无新Migration。
历史v7/v8与新v9均须由兼容Reader读取；保留0044，按既有开关停止新写/claim，不清run/事实。

策略列表仅复用CandidatePool已有useElementSize与原DataTable列配置：去掉强制scroll-x1510，
保留9列（含最近结果）、左策略名/右操作固定标记、启停/编辑原位响应及Query分页/过滤/滚动。
以实际容器宽度减2px边缘预算，状态68px、操作192px保留；剩余文本按权重分配。
达人列至少84px、渠道至少96px（常规支持窗口），其它name/shop/conditions/execution/result共享剩余，
名称/摘要及长字段沿Naive ellipsis悬浮完整查看。无字体/主题/shared表格API/overflow裁切补丁。
四主题与1280/1440/1920的浏览器全API拦截检查只是渲染/交互证据；普通/最大化唯一Electron由ca97补验。
A本增量通过即按独立Gate/Release交Main，不等待B/达人/手机；原生测量工具超时按具体限制登记，不代标通过。

## 2026-10-14 A收尾：候选池实际宽度与目标页

本轮直接人类任务已确认a75品牌保存回显、策略九列普通/最大化及page2启停编辑原位，
ca97保留该验收及两种品牌正式闭环，不重复索取；仅补本节影响，A发布不等待B。

新手动请求先沿原日期/品牌/价格冻结，再计算目标页ceil(rank_from/10)至ceil(rank_to/10)，
有序加入一次首页。150–200为[1,15,16,17,18,19,20]；第1页用于现有日期判断，按官方rank
过滤后才写事实，不能把探查首页的目标外商品先入库。同一实际窗口首页复用，不二次请求。
合法空或原已批准精确业务码的有限备窗规则、非默认品牌/价格禁止业务探查、基本信息失败保护不变。
每次改变日期仍重新签名；正式总数在跳目标页前再次限制页起点，不补齐不存在的排名/条数。
第一页/目标页后续失败不无限前移窗口；官方rank/首次上榜bool筛选和商品去重不由本地行号代替。

默认品牌只有页序列确实变化的新Run使用v8；非默认品牌新请求统一使用纠正映射的v9，并直接保存
精确有序目标页。历史v1–v8的JSON/hash/原页序列不改写、不放宽；v8仍用不持久化/不签名的
旧序列投影复用历史条件校验，v9投影只用于日期/价格校验，不改变实际签名或发送值。
旧活动Run同条件仍按旧hash复用canonical及旧冻结序列；新回执不得把旧执行伪装成已优化。
写v9后回滚必须保留v8/v9 Reader，不能直接换回a75旧Backend；0044、Run、失败和事实保留不清库。
无Schema/Migration、无Signer/Session/并发/调度变化。

候选池保留原12列、64×64缩略图、详情图、14px正文、8×12px padding、固定勾选/图片与右操作。
取消1496的强制scroll-x，以现有useElementSize/DataTable列配置读取容器预算（减2px），
勾选44/图片88/操作220保留。数字/状态列在紧凑54/66/80/84/106/82与宽屏88/88/112/96/140/100
之间按宽度平滑增长，剩余供标题/商家/类目；商家至少66、类目至少52，长文本ellipsis+完整tooltip。
标题阅读容器上限360、居中两行；需要时表头自然换行，不缩字号/删列/父级裁切。
价格带保留原值并提供完整hover，普通数据/缺值/排序/消息/操作及原12px动作间隔不变。
四主题/1366、1440、1920、2560实际浏览器截图与交互不是原生验收；ca97同一Real Electron复验。
