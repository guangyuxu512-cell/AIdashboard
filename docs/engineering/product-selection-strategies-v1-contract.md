# 罗盘选品策略 A / 服务端定时 B 契约

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
Team/Shop 过滤再搜索/分页。写入重验有效 Team/启用且未删除抖店；超级账号写入仍需明确 Team。
Team 仅剩策略也阻止物理删除，不能让新表产生未解释的级联数据丢失。

关闭策略（enabled=false）只要求当前Actor/Team/Shop可见授权和版本CAS，不要求该店铺
执行就绪，也不读取Session或请求平台。重新开启仍要求所关联店铺启用、未删除且为抖店；
实际执行继续独立复核资格和Session。新建/完整保存校验本次提交的目标店铺，仍拒绝停用目标。
编辑旧停用目标换到另一已授权启用抖店允许；原配置的访问权限/CAS仍校验，不能借新目标绕过旧配置撤权。
仅在旧停用目标上改名称的完整PUT仍明确拒绝，应使用关闭PATCH或选择合法新目标，不泛用旧目标执行校验。

- GET `/api/v1/product-selection/strategies`：分页/名称查询，批量附最近真实执行摘要；
  无结果就是 null，不伪造一次运行。关联回执解析到其 canonical 执行。
- GET `/strategies/{strategy_id}`：已保存相对条件、计划草稿、version 和 enabled。
- POST `/strategies`：保存配置，不请求平台、不提交 run、不启用调度。
- PUT `/strategies/{strategy_id}`：完整编辑＋expected_version；CAS冲突保留客户端草稿。
- PATCH `/strategies/{strategy_id}/enabled`：expected_version＋enabled，同一授权/版本边界。
- POST `/runs`：增加可空 strategy_id；执行当前提交条件，不读取策略覆盖草稿，不顺带保存。
  已保存策略须同Team/Shop可写；未保存草稿保持无策略关联。相同submission_key重放
  同时检查条件和策略关联，不能跨策略挪用回执。不同key的相同活动条件仍复用已有执行。

POST关联策略时须同时提供strategy_id和strategy_version（正整数）；服务端锁定同Team/Shop
当前策略并核对版本，保存v3（7d）或v4（实时）request_conditions.strategy快照。后续编辑不改任何旧run。
不同策略复用活动条件时，canonical身份/版本不改；每个reused回执保存自己的策略快照，
提交响应的strategy表示调用者快照，execution表示canonical计数/状态/冻结条件。
按回执ID GET仍沿旧契约解析canonical；策略列表按各自提交回执批量取canonical最近结果，
并再次按历史请求Shop的当前授权过滤，换Shop后撤销旧Shop不能泄露旧run。

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
| 近1天/近30天 | 尚未冻结各自Query/成功Response/页面含义 | 独立门禁，收到各自证据再接，不猜昨日或30日枚举 |
| 行业/类目 | cate_list 多根/有序节点；原成功行业7 | 核验其它根的行业含义和父级路径，不发送0或UI `/*` |
| 品牌 | -1＝不限有成功样本 | 其余枚举需补证，不猜0/1 |
| 价格 | price_bin=不限有成功样本 | 自定义格式、边界与单位待直接证据 |
| 首次上榜 | product_info.newly_on_ranking 为平台布尔标记 | 按该返回标记筛选，不以本地first_seen代替；未知不当false |
| 排名 | product_info.rank 官方原值，page_result总200已有证据 | 有界分页，按官方排名1–200筛选，不用本地行号 |

平台最少补验由ca97使用环境合法Session协调。Feature只用合成响应；不索取Cookie/cURL，
不重复旧成功试验、不将 HTTP200 或模拟数据算成新业务成功。

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
未知周期、品牌、自定义价格及其它行业分别取得Query＋HTTP/业务成功Response/页面含义后逐项实现，
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

兼容回滚使用最终候选（支持v4实时run/来源、旧v1/v2/v3及首次上榜来源）的Backend Reader，
写入v4后不能直接换成77a1d96/3128等旧Backend，即使先关闭UI/执行开关也不等于兼容。
将上述两个开关写入既有受保护部署配置并按规范重启，停止新提交/claim；已发网络请求不承诺撤回。
必要时用既有SelectionRunService.recover_expired在租约过期后记录interrupted，保留事实/回执，
不自动重发；旧执行者仍受DB时钟/lease fence保护。可以回退Renderer，但Backend Reader及0044保留。
Feature已验证只读开关和数据保持；真实部署/重启流程仍须ca97/Main Release核验，不作已发布声明。

本轮尚在契约审核/开发，A/B均未完成；独立记录合成、PostgreSQL、真实平台和Electron证据。
真实到点自动执行必须通过B的Integration闭环，手动调用执行器不能替代。
