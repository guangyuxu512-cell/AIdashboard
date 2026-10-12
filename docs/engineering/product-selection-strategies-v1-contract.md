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
当前策略并核对版本，保存v3 request_conditions.strategy快照。后续编辑不改任何旧run。
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
| 实时/近1天/近30天 | 实时已有 Query=1，但旧证据不含Response；其它尚未冻结 | 需明确枚举与区间；无证据不解除禁用 |
| 行业/类目 | cate_list 多根/有序节点；原成功行业7 | 核验其它根的行业含义和父级路径，不发送0或UI `/*` |
| 品牌 | -1＝不限有成功样本 | 其余枚举需补证，不猜0/1 |
| 价格 | price_bin=不限有成功样本 | 自定义格式、边界与单位待直接证据 |
| 首次上榜 | product_info.newly_on_ranking 为平台布尔标记 | 按该返回标记筛选，不以本地first_seen代替；未知不当false |
| 排名 | product_info.rank 官方原值，page_result总200已有证据 | 有界分页，按官方排名1–200筛选，不用本地行号 |

平台最少补验由ca97使用环境合法Session协调。Feature只用合成响应；不索取Cookie/cURL，
不重复旧成功试验、不将 HTTP200 或模拟数据算成新业务成功。

## B 预定扩展边界（未实现）

同一 Schedule 底座明确区分 PC 与 server_selection，设备必填仅适用于PC；选品关联策略，
到期调用正式选品服务创建run，不生成虚假Task或Device。新增hourly＝上海整点，daily＝用户上海时间。
用既有unique(schedule_id,scheduled_for)、短事务claim、COALESCE ONE恢复；同策略活动轮次不重叠。
PC读取API在服务端排除选品记录，不靠前端隐藏。迁移待A完成后另申请登记。

## 迁移与验收

ca97已登记并确认唯一active Slot `20261013_0044_product_selection_strategies_v1`，
revision `20261013_0044`，down `20261010_0043`。Feature已应用并验证迁移闭环，
Integration/生产仍0043；禁止改写0042/0043或通过降级清库绕过记录保留。
已分配Feature库 `control_center_feat_product_selection`，角色 `control_center_dev_user`；
8101/4176 strictPort，35433受信任隧道由ca97恢复。实际Feature为单一0044，
47业务表＋alembic_version（public共48表），末次ShopSession/策略/run均0；
应用角色无CREATEDB/CREATEROLE/SUPERUSER，不复制生产凭据。
升级保留旧候选/观察/run；降级仅可重建库且无新策略/关联run时允许，否则fail closed。
正式应用回滚保留Schema/策略/事实/失败记录，用兼容Reader关闭新写/新执行，不清库。

兼容回滚使用本候选（支持v3 run及v2首次上榜来源）的Backend Reader，不能直接换成3128等旧Backend。
将上述两个开关写入既有受保护部署配置并按规范重启，停止新提交/claim；已发网络请求不承诺撤回。
必要时用既有SelectionRunService.recover_expired在租约过期后记录interrupted，保留事实/回执，
不自动重发；旧执行者仍受DB时钟/lease fence保护。可以回退Renderer，但Backend Reader及0044保留。
Feature已验证只读开关和数据保持；真实部署/重启流程仍须ca97/Main Release核验，不作已发布声明。

本轮尚在契约审核/开发，A/B均未完成；独立记录合成、PostgreSQL、真实平台和Electron证据。
真实到点自动执行必须通过B的Integration闭环，手动调用执行器不能替代。
