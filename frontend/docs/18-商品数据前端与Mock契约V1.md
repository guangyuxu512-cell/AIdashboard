# 商品数据前端与 Mock 契约 V1

## 字段白名单与稳定排版增量

2026-10-17按用户确认的字段范围追加纯前端修订。`model/display-fields.ts` 是列表、字段配置和详情共同使用的唯一展示白名单；它只引用既有17项指标定义，不复制来源代码、单位、格式或数值。基础字段为店铺，商品信息／ID固定在列表左侧，操作固定在右侧。其余固定顺序如下：

- 核心指标：曝光、点击量、点击率、加购量、加购率、真实订单、异常订单、转化率、退款率。
- 交易指标：支付金额、订单数、成交人数、客单价、退款金额、退款单数。
- 流量指标：曝光人数、点击人数、曝光点击率、点击成交率。

流量组的曝光点击率与核心组点击率共用 `exposureClickRate`，点击成交率与转化率共用 `clickPayRate`。两个展示别名只有独立显隐，不新增采集指标、请求字段、行数据、数据库列或计算口径；排序仍发送原17项平台代码。退款率继续使用支付时间总体口径，包含发货前后，不恢复发货后退货率。可售库存没有核实来源，本轮不展示、不补0。

新用户默认显示店铺和完整核心组。个人偏好键与按用户隔离不变；读取旧偏好时只保留白名单内的显式选择、迁移既有比率／退款率替代ID并去重，再按固定业务顺序呈现，不自动回写或清空存储。结算金额、退款时间旧口径、旧未核实退款单数、库存、商品分组、售卖类型、载体和数据时间继续保留在底层兼容模型，需要时可由后续明确任务处理，但不再进入当前列表、字段配置或详情。

列表不再按容器动态拉伸中间列。选择列44px、商品信息304px、操作88px，店铺140px，既有指标宽度130px或150px；每列同时设置width、minWidth和maxWidth，空间不足时只在表格内部横向滚动。字段配置按基础／核心／交易／流量固定分组，勾选先后不改变列序。详情按同一四组使用既有Descriptions与Design Token形成单列标签和值布局，抽屉正文承担纵向滚动，窄窗不产生页面横向溢出。共享表格、全局主题、compact密度和默认20条不改。

本增量没有Backend、API DTO、17项原映射／单位、74字段采集、日期、调度、Migration、依赖、Electron或Worker改动。Owner前端全量169文件918项、商品数据浏览器24场景、eslint、vue-tsc、Real生产构建及默认Verify均通过；Verify仍为28项精确已知未修复、0新增、0 stale。真实Integration Electron及人工新界面确认留待ca97 Gate 2，不复用旧截图冒充本候选验收。

当前增量：商品数据真实接入首里程碑，Owner 7d55，feat/shop-product-data-real-v1，
正常no-ff保留af6/d3并同步精确Green a6df9ac（原Green157实现保留，运行业务不变）。已接正式GET列表、POST手动采集和GET回执，契约以Backend05/26为准；
Feature DB control_center_feat_shop_product_data、8102/4177与active0047由ca97登记。未部署、未新增窗口。

Real在SQL分页后只映射当前页，不本地筛选或重新计算total。17指标按registry精确映射，有效unit5计数显示原整数，
使用BigInt格式化不损精度。官方商品列表cell_info→EUE→formatter链已核定金额unit3原值除100为元、比例unit4保原分数并显示乘100%。只有Backend已核定且unit匹配才应用；保留rawValue/rawUnit，unknown/无效/unit6不补0。金额规范值与最终2位金额/百分比均不经Number转换或提前舍入。
旧四列保留未知。selling/carrier为null，不把baseline1/1猜成自营或商品卡，groupingAvailable=false不伪称未分组。
Real开放五数量/四比例区间与17指标排序，均由Backend全量SQL执行。比例UI填1表示1%，精确发送0.01；复用同一Zod验证与现有数字输入，发送前从其规范十进制文本移位，不发Number除100的尾数。单边及[min,max)保持，数量超安全整数范围拒绝。分组、自定义、其它售卖/载体及四旧兼容列筛选排序仍不支持。
页面只在环境collectionAvailable=true且查询已选单店时开放“更新数据”，不因进入、筛选、翻页或刷新发POST。
提交失败保持同一submissionKey供显式重试；成功回执按精确ID轮询GET，完成后失效事实Query，读失败只重读不重提。
人员/Team/Shop/期间变化拒绝旧UI结果；平台执行仍由服务器当前授权和lease保护。失败不加载Mock。

单位证据与三窗口21个非零原数值独立公式回归见工程shop-product-data-unit-contract-evidence-20261017.md。保留core17_v1、来源/序列hash及原三成功代；旧unit_complete_rows=0不回填，当前GET的单位核定不冒充当时采集覆盖。新候选仍需ca97独立Gate2/页面验证，不将旧178/229/344采集结果记成新UI验收。

失败回执failureCode=PRODUCT_DATA_COLLECTION_LIMIT_EXCEEDED时，原StatusTag显示“超出采集上限”，原Tooltip展示冻结窗口、可用的expectedTotal及“本次未发布，已有成功数据保持不变”；总数未知不补0。只消费Backend05现有字段，不猜当前环境上限数值，不自动重试或放宽预算。历史PLATFORM_RESPONSE_INVALID仍按原通用失败展示，不据阶段或0页倒推改写原因。

以下保留UI与Mock历史。其“未接入”描述对应当时阶段，不覆盖上述新Real边界。
原UI基线9bb64ac、独立4177，旧阶段没有Feature DB或Migration；人工和Integration Electron未覆盖项仍保留。
2026-10-16在原分支正常no-ff同步精确Green5a18bd0390cb4b8cbed637d412f7482cefff3f36，
同步当时本模块运行代码/Mock与141修补保持不变；随后指标筛选增量见下文，Green已有0046代码不构成本页DB/API授权。

## 复用与边界

| 已有能力 | 本次处理 |
| --- | --- |
| Module Registry、Router、Shop Guard、Auth Context | 商品数据作为数据中心独立页面，复用 shop 授权；不增加后端权限码 |
| ManagementListSection、FilterBar、DataTable、PaginationBar、AppDialog/Drawer | 组合现有组件，不新建表格或弹层框架 |
| 选品 ExternalProductImage | 提取到 Product Entity，原组件保留兼容包装；候选池布局不变 |
| 用户隔离的 localStorage 偏好模式 | 字段偏好按 userId 保存，只存列 ID 和顺序 |
| ShopSession、HTTP/Signer、经营采集与调度、通知通道 | 只读盘点；不调用、不新增后台或复制凭据 |
| 商品数据查询、店内商品分组 | 新增明确的前端 ViewModel 与隔离 Mock，不冒充正式 API |

入口为 /product-data，moduleCode 为 product-data、accessModuleCode 为 shop。页面没有重复标题或副标题。
默认固定商品信息（图片、标题、字符串 ID、复制），可配置列默认包含店铺、商品分组、
曝光人数、转化率、订单数、结算金额；点击人数等可选。结算金额是对旧 receive_amt 误标的纠正，
不将用户支付金额、成交金额和结算金额合并。
商品标题复用共享 ProductInfoCell 单行省略及 NTooltip 悬浮全文，ID 保持独立一行并显示“ID：”前缀；
复制仍只提交纯字符串商品 ID，不含前缀。长标题不能增加行高或列宽。
ID 行使用紧凑的统一文字槽与独立复制按钮槽：文字槽最多使用现有 sm 字段宽度，
按钮保持 compact 控件宽度，各行按钮不随 ID 长度漂移，也不推到整个商品列最右侧。
窄容器只收缩文字槽并省略，按钮不收缩；溢出的 ID 通过共享组件悬浮查看完整字符串。
显式开发 Mock 预览 productDataPreview=mixed-ids 提供短/18位/超长字符串测试样本；
默认样本不变，Real 不启用此场景或加载样本模块。
全表宽度由可见列累加，横滚只发生在表格，商品信息固定在左侧。

2026-10-15紧凑接入：正常no-ff消费ca97交付的纯共享
1a8078d0cd9917afc11454e84ff0d13d15a1a2f2及Radio修补
141fec65d413566987c84c79cc172fe4e32216cb（均不是Green dev）。本页列表、筛选、分页和工具栏
显式使用compact，商品图48px、复制槽28px，表格沿共享主题细竖线与原有对齐。
商品列使用本页304px预算，宽屏剩余空间分配给现有数据列，不照搬候选池列宽。
详情/分组管理/批量分组/字段配置VNode移到局部主题边界外，内部保持原默认，详情图仍64px。
共享Radio修补消费后，原4个尺寸失败断言均按原期望12px/28px通过，四主题同样实测通过。
本轮Gate 1通过，仅UI_ONLY范围；ca97 Gate 2及商品数据人工验收仍待完成，不据此发布。
原b2草稿/失败证据保留，紧凑阶段交接见shop-product-data-compact-v1-gate1-20261015.md；
指标筛选原交接见shop-product-data-metric-filters-v1-gate1-20261016.md；
退款率阶段修正见shop-product-data-refund-rate-v1-gate1-20261016.md；
最新字段核实接回见shop-product-data-verified-metrics-v1-gate1-20261016.md。

## 数据与查询草案

types.ts 是本阶段 Frontend ViewModel 和 service 的唯一类型源，不是 FastAPI DTO 或数据库模型。
列表 Query Key 包含 actor context、已应用筛选、日期、排序及分页。字段修改是草稿；
查询/重置回到第一页并清除勾选，换页清除勾选。切换店铺清除不兼容的组选择和弹窗；
切换人员/团队重新挂载工作区，旧异步返回不能覆盖新上下文。
本页初次进入默认每页20条，可切换既有10/20/50/100选项；切换条数回第一页并清除勾选，
后续查询/重置/排序保留当前所选条数。不改其他模块默认值，不新增分页存储或清除已有列偏好。

Mock 使用虚构商品，查询顺序固定为完整数据集筛选 → 全量排序（缺失最后、稳定 ID）→ 分页。
统计日期按 Asia/Shanghai，快捷项为昨日、近7天、近30天及自定义。Mock 数值只模拟所选期间，
不从响应样本推导金额换算，不把示例数当实数；比例由合成期间的分子/分母生成，不平均逐日比例。
售卖、载体和更多筛选仅在显式 Mock 演示中可用，其真实平台请求参数仍待证据。

指标保留 available / missing / null / invalid，0 正常展示，缺失显示 — 并可查看状态。
核心字段的旧偏好兼容边界：

| 旧前端 ID | 当前展示 | 边界 |
| --- | --- | --- |
| product_show_ucnt | 曝光人数 | 对应商品曝光人数，不是次数 |
| product_click_ucnt | 点击人数 | 对应商品点击人数，不是次数 |
| product_click_pay_ucnt_ratio | 转化率 | 只在偏好入口迁移至 clickPayRate；平台正确 code 为 product_click_pay_converse_uv_rate，不再作为指标字段使用旧 ID |
| pay_cnt | 订单数 | 目标口径为成交订单数，不是件数 |
| receive_amt | 结算金额 | 旧响应已纠正名称，不能与 pay_amt 或 trans_amt 互换；缩放未定 |

最初盘点只有响应和 meta，page_no=1/page_size=10/total=31；后续请求与响应由 ca97 独立核验，
不把不同周期、载体或采集时点的样本混为一次结果。金额 unit=3 的实际缩放仍未知。
原UI_ONLY阶段Real service显式不可用；当前Real实现见本文开头及Backend05/26。
Mock仍不代表真实采集，分组未接入不伪造成功；此历史阶段的金额/比例单位待核限制已由本文开头的官方路径核定替代，不以Mock作为换算依据。

## 分组草案与偏好

分组属于单个店铺。当前单组归属只是最小前端演示提案，待规划确认，未声明正式后端关系。
初始无组，允许创建、重命名、对当前页勾选商品批量设置/移出。
不同店铺的商品不能提交同一次分组变更；相同组名可在不同店铺独立存在。
删除组前提示受影响商品数，只移除组归属，保留商品、指标与其他店铺组。
Mutation 失败保留完整草稿及弹窗，可重试；成功后失效 Query 并重新读取。
Mock 组只存在当前工作区内存，刷新后恢复未分组，不声称持久化到服务器。

个人字段偏好键为 control-center.product-data.columns.v1.<userId>，保存有序可见列 ID；
商品信息和详情操作不允许隐藏。格式无效时恢复默认；保存失败保留配置弹窗及草稿，
不提示已保存。没有人员身份时不写共享匿名偏好。

## 指标命名与九项区间筛选增量

2026-10-16 规划聊天人类 turn `01a1446a-0a38-75a1-b3b4-4a348c4d8651` 正式分配本增量。
沿原分支和 b9fa5717 候选接续，17 项目标名称来自人类 turn `01a14457-9a36-7cd3-a8e0-60b8aef1911f`。
本阶段仍只有前端与 Mock，不增加 API、采集、持久化、日期回退、迁移或调度。

`model/metrics.ts` 是商品数据内展示名、官方口径提示、别名和格式的唯一注册。
id 用于 UI/偏好；platformCode、rawUnitCode 登记 ca97 单页核实的来源代码与当前值单位，不是正式 API DTO、
Real mapper 或缩放契约。比率改用独立语义 ID，旧错误代码只留在偏好兼容入口，不能拿来请求平台。

| 展示名 | 官方名称 | 前端语义 ID | 已核实 platformCode | 当前值原始 unit |
| --- | --- | --- | --- | --- |
| 曝光 | 商品曝光次数 | exposureCount | product_show_cnt | 5 |
| 点击量 | 商品点击次数 | clickCount | product_click_cnt | 5 |
| 点击率，别名曝光点击率 | 曝光点击率（人数） | exposureClickRate | product_show_click_converse_uv_rate | 4 |
| 加购量 | 加购人数 | cartUsers | click_add_to_cart_uv | 5 |
| 加购率 | 访问加购转化率 | visitCartRate | product_add_show_converse_uv_ratio | 4 |
| 真实订单 | 净成交订单数 | netOrders | net_pay_cnt | 5 |
| 异常订单 | 退款后成交订单数（支付时间） | refundRelatedOrders | pay_cnt_exclude_refund | 5 |
| 转化率，别名点击成交率 | 点击支付率（人数） | clickPayRate | product_click_pay_converse_uv_rate | 4 |
| 退款率 | 退款率（支付时间） | payTimeRefundRate | pay_refund_ratio | 4 |
| 支付金额 | 用户支付金额 | pay_amt | pay_amt | 3 |
| 订单数 | 成交订单数 | pay_cnt | pay_cnt | 5 |
| 成交人数 | 成交人数 | pay_ucnt | pay_ucnt | 5 |
| 客单价 | 成交客单价 | payPerOrder | per_user_price | 3 |
| 退款金额 | 退款金额（支付时间） | payTimeRefundAmount | pay_refund_success_amt | 3 |
| 退款单数 | 退款订单数（支付时间） | payTimeRefundOrders | pay_refund_success_order_cnt | 5 |
| 曝光人数 | 商品曝光人数 | product_show_ucnt | product_show_ucnt | 5 |
| 点击人数 | 商品点击人数 | product_click_ucnt | product_click_ucnt | 5 |

19 个中文名称只产生 17 项目标指标，两组比率别名不增加列、查询指标或存储副本。
表头、详情与字段配置均复用口径 Tooltip；异常订单提示退款相关而非风控，净成交与退款后成交不相减推算。
旧结算金额、退款时间金额、未核实退款单数及库存四列作为兼容项保留，不算进 17 项目标；
旧 refund_amt 不重绑支付时间退款，refund_cnt/stock_cnt 显式未知。原有偏好键、可见性与顺序保留，
读取只规范同义别名并去重，不改写 localStorage；显式保存才写入，恢复默认仍沿既有列集合。
旧 product_click_show_ucnt_ratio / product_click_pay_ucnt_ratio 分别只在此偏好入口迁移为
exposureClickRate / clickPayRate，保留原可见顺序并去重，不作为平台代码或指标数据别名。

同日人类 turn `01a1449d-2ad6-7ce0-8145-2e1ecb0a3a61` 明确改用总体“退款率（支付时间）”，
包含发货前与发货后，替代先前发货后退货率目标；17 项独立指标数不变。
展示列与筛选均为“退款率”。旧 shippedReturnRate 仅在列偏好读取时迁移为 payTimeRefundRate，
保留可见位置并去重，不自动回写；旧数据、筛选与指标别名不迁移，不把两种口径视为同义。

售卖类型采用全部/自营/合作，载体采用全部/直播/短视频/商品卡/图文。
`self/cooperation`、`card/video/live/image-text` 是 Mock 枚举，不直接当作平台 sale_type/content_type。
店铺、ID、名称与分组继续组合使用。九项区间默认不限，只有选自定义才显示上下限，支持单边界、清空及重置。

| 指标 | 预设边界，最后一档无上限 |
| --- | --- |
| 曝光 | 0 / 1000 / 3000 / 5000 / 10000 |
| 点击量、加购量 | 0 / 10 / 50 / 100 / 200 |
| 点击率、转化率 | 0% / 1% / 2% / 4% / 6% |
| 加购率 | 0% / 5% / 8% / 10% / 15% |
| 真实订单 | 0 / 5 / 10 / 50 / 200 |
| 异常订单 | 0 / 5 / 10 / 20 / 50 |
| 退款率 | 0% / 10% / 20% / 30% / 50% |

预设和自定义统一 `[min,max)`；末档 `>= min`，空边界不限。两边均空不限制未知值；任何有效边界都排除缺失、
空、无效、非有限及错误单位值，合法 0 仍正常参与。边界为非负有限值，数量须为整数，同时填写时 min 必须小于 max。
截图遗漏的转化率 4%–5% 已按连续 4%–6% 档覆盖，不照搬缺口。自定义上下限纵向排列，避免窄控件的数字被步进按钮挤压。

`model/metric-ranges.ts` 以 Zod 校验草稿，View 复用 vee-validate 管理错误。
页面百分比 1 明确表示 1%，编译为 Mock 内部 fraction 0.01，数量不缩放。
`ProductMetricInterval` 显式包含语义 metricId、min/max、含下限/不含上限和 count/fraction 单位，
是未来查询的前端草案，不是正式 DTO；平台原始 unit 3/4/5 与金额缩放不在此转换。
完整 Mock 集合先按全部组合条件筛选，再排序、计算 total、分页，筛选不触发采集。
查询成功回第 1 页并清除勾选，非法草稿保留原结果与页码；隐藏字段不清除筛选，草稿深复制后才进入 Query。

ca97 本次 74 指标结果已于上海 2026-10-16 20:42:43 成功：固定 2026-10-14、type20、page1/size10、
sale1/content1，HTTP200/st0，10 行、total146；17 项各有 10/10 有效当前值，共 170/170，含显式零。
本树离线逐字段核对代码、当前值及原单位一致，不复制这些真实值到 Mock；单页不能代表 146 件全量或其它维度。
unit 来自 cell_info 当前值节点，不把 meta 存在当逐行有值；目标外 7 项部分只有 unit6 无 value，继续不补 0。
net_pay_cnt、pay_cnt_exclude_refund 的 meta.tip 均为空，不证明全额/部分退款算法。
同一商品原值成交102、净成交97、退款后成交95、支付时间退款订单7，95不等同发生退款的7单。
用户选定“异常订单”别名保持，但 Tooltip 明示不等同发生退款订单数；业务解释交规划确认，不自行相减造字段。
退款率目标 code 已复用 ca97 既有 70 指标成功响应离线核对为 pay_refund_ratio：
meta 为“退款率(支付时间)”，tip 为“退款订单数(支付时间)/成交订单数”；10 行有 3 正值、7 显式零，unit4，
首行原值 0.10384608086826178。直接保留平台总体比率，不自行相加发货前后百分比、重算覆盖或以退款时间指标替代。
sold_pay_refund_ratio 只是发货后退款率（支付时间），不得替代总体退款率。
本次 74 响应再次确认该字段为 3 正值、7 显式零、unit4；本树只离线接回证据，未追加请求。
上述历史单页核验时没有真实mapper/API或单位对照。当前核定依据已补独立官方商品路径及三个窗口真实原值，见本文开头；
不由其它业务字段重算比例，不将旧单页或Mock的yuan/fraction当成换算证据。

## 验证边界

覆盖全量排序、日期/筛选、缺失与0、分组从零开始及跨店保护、失败重试、字段偏好隔离、
人员/团队上下文切换、普通/最大化浏览器与弹层视口。生产 Real build 与接口未接入回归独立验证。
浏览器证据不替代真实 Integration Electron，真实数据采集、数据库、定时、飞书均未覆盖。
