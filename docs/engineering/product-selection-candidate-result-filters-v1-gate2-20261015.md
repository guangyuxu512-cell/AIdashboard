# 候选池结果与基础信息 Gate 2 集成记录

当前精确Candidate为 `bfaae14d76780f031e34ef68b139a26bb19b8694`，直接父为
`9734809530f42046293a83c967611f0ac82c07a5`，继承f876/51852。技术、Integration数据库/API及用户
提供画面的商品信息/首次上榜界面确认通过；原生剪贴板、普通/最大化专项未单独取证，不补写通过。
真实平台单项基础更新尚未完成，Gate2整体保持进行中，不把界面确认当作平台取数通过。
此Feature未获生产发布授权；本次未访问生产，最后已记录生产为B
`382ca92ee1f415e0e1a4269de6b9a02c382e114d`/0045，不冒称已部署本候选。

## 候选与技术检查

Owner81a1，分支feat/product-selection-candidate-result-filters-v1，基线为精确Green
`9bb64ac76bf9e0f51fb1715517cf8c18cef63e22`。最终51852cc6只在功能提交df3d4cb后整理迁移测试EOF。
ca97使用本地ignored不可变Git归档，不把Owner工作目录或治理HEAD当运行版本。

独立检查覆盖当前授权重验、Team商品全来源屏蔽、desired-state原子审计、canonical批次关联和冻结排名，
今日匹配命中后商品去重、旧明细未知、价格规范化发现键，以及basic操作共用原Run/Executor/容量/租约fence。
basic仅更新已确认基础字段，saved_count=0、无策略/计划，保留旧rank状态与视频事实。
Migration46在线预检旧约束名称，降级在DDL前限制精确可重建Feature并拒绝任何新语义。

Backend独立默认807项通过，新增相关纯逻辑14项另行通过、不叠加统计；Frontend选品/Selector/Audit
17文件124项通过，lint/typecheck/Real build通过。仅既有httpx弃用与大于500kB分包警告。
Owner66个Feature PG场景和四主题API拦截截图属于Gate1证据，未当作原生或平台成功。
Electron源码与现有ce3/1.0.6壳相同，无新安装包需求。
候选内容及本地敏感值检查仅输出计数：敏感匹配0、禁止artifact0、冲突0、diff check错误0；
锁定依赖及42–45旧迁移相对Green保持不变。

## 共享选择器返修与人工确认

f876f83仅修复长名称悬浮展示，复用AppSelect/ShopSelector与现有Naive NTooltip，
labelTooltip默认false，仅在候选池请求店铺、策略、批次及策略抽屉请求店铺显式启用。
选中值与下拉项保持单行省略，仅溢出时显示全文；搜索焦点、点击、键盘、清除及自定义标签兼容。
不改控件宽度、全局样式、Backend、Electron、依赖或已应用0046。

ca97对精确归档独立复验18文件134项、lint、typecheck及Real build通过。
Owner四主题/两尺寸浏览器API拦截验证通过，仍与原生人工证据分开。
初次NEllipsis点击异常已在候选内改用NTooltip修正，不升级或修改依赖。

2026-10-15用户在本聊天直接确认：“刚才说的策略，界面。都验收通过”。
本次确认登记为当前策略界面及长名称悬浮展示的人工通过，不重复要求这部分验收。
确认时5180实际来自f876f83封存归档，严格Real/8100代理，已编译模块包含标签修复及调用点启用。
8100仍来自父51852，Backend源码与f876f83逐字相同；唯一开发Electron为现有匹配1.0.6，原Profile保留。
未把此前A/B、浏览器合成截图或该人工结论记作本候选真实平台基础更新成功。

## 商品信息、首次上榜增量及人类确认

9734809仅从既有商品实体复用ProductInfoCell/ProductImage与薄兼容Facade，合并图片/标题，
单行标题、独立原字符串ID及复制槽；缺ID显示—并禁复制。ca97独立19文件140项、lint/typecheck/
Real build通过，17份候选文件/清单/锁文件blob一致，不更改Backend/Electron/依赖/0046。
bfaae14在排名右侧增加84px首次上榜列，直接复用dto.newly_on_ranking → row.firstListed；
列表与详情共用严格true/false/null的“是/否/—”，不从发现情况/上架日期推算，不加筛选或排序。
ca97对精确增量独立3文件18项、lint/typecheck/Real build（16.24秒）通过，13份归档blob一致；
未变973等证据按范围复用，不累计为新增测试。Owner四主题浏览器/全API拦截只作补充，不作平台或原生证明。

当前5180已正常更新为bfaae14封存归档，实际服务模块与原生可访问树包含商品信息/首次上榜，
当前第1页、29条候选。8100仍为与本候选逐字相同的51852 Backend；同一Electron1.0.6/Profile/
人员会话保留，无第二实例、迁移、业务写入或本Feature平台请求。HuanYu valid v6，11类原表计数保持。
原生树可读的现有样本：IVSO按压切蒜器3846580557572080245为否，火锅盘3847090073610879415为是；
明确标注“非平台证据”的G2合成商品9999000046001001为—。三者不混用为本候选真实basic执行成果。

2026-10-15 ca97直接回读规划聊天 `01a13b33-8508-7ee2-916d-8e1009cb2209` 的人类
turn `01a13db6-ba41-7520-86f3-4f65d62a9fc2`、消息 `01a13db6-bb67-7140-98f2-6dd25b5b6a59`：
用户附当前候选池截图并明确“验收没问题”。截图可见商品信息、原字符串ID/复制入口以及首次上榜
是/否/—和原29条数据，与上述匹配运行现场一致，登记为当前可见界面人工确认，不重复该界面验收。
截图本地受忽略保存，SHA256 `3C2789CDEBB46BB33D53FF321A3F438952081660A1CD43FE1EC545BE2F9464CC`；
原图/路径、PID及详细机器记录不提交Git。它不包含可证明系统剪贴板结果或普通/最大化两状态的证据，
这些项目只标“未单独取证”，不倒写通过，也不把用户整体确认夸大为全部Gate2或发布授权。

用户当时同时提出参考观星树字体/下拉框的整体观感评估，当时仅由规划只读评估。
随后获批的显式紧凑列表任务及顺序见下一节；不是全局默认改造或残留代码/Mock清理授权。

## 新增授权：共享紧凑规格与分阶段验收

已直接回读规划人类turn `01a13dba-08ad-7992-977b-42350767e6a3` 的“按照你这个，分别给任务”，
及前置三层范围说明；新授权替代仅只读评估的阶段限制，不扩大生产发布权限。
当前仍保留已确认bfaae精确运行环境/数据，未加载或声称实现尚未交付的紧凑Candidate。

| 层级 | 已批准范围 |
| --- | --- |
| 显式紧凑列表 | 表头/列表内容/ID12px；筛选标签13px；筛选输入/下拉/按钮28px且文字12px；间距8px、卡片内边距12px；列表图48px，行高目标约64px但不得裁内容；分页/批量栏匹配 |
| 页面配置 | 各页原业务字段、列宽、固定列、筛选、操作与必要横滚；标题单行/全文悬浮、ID原字符串独立行及固定复制槽保留 |
| 不改默认 | 字体家族/全局字号/导航/顶部栏/主题/圆角；店铺/经营等其它模块；详情/编辑表单内部；summary80/默认thumbnail64及原权限/复制/图片预览重试 |

唯一共享Owner81a1，ca97只审核/登记/集成，不代写。新短期共享分支从重新核实的Green
`9bb64ac76bf9e0f51fb1715517cf8c18cef63e22` 创建，CI
[38597874343](https://github.com/guangyuxu512-cell/AIdashboard/actions/runs/38597874343)三job success。
ca97治理提交不是新Green。原bfaae分支与7d55 b364成果保留，不reset/rebase/强推、不新建worktree。

共享分支`feat/compact-product-list-foundation-v1`只承载Shared/列表模式/商品实体及必要ShopSelector
透传、测试/契约；仅经审最小商品信息/长标签前置，不整合选品0046业务或商品数据模块。
共享接口方向接受`ListDensity = 'default' | 'compact'`，现有组件默认default，局部复用
Naive NConfigProvider abstract；父主题合并必须不可变并响应主题，不建立新Provider框架。
独立list-compact命名Token只供显式调用，不改变现有默认Token引用。经核验例外只允许
ExternalProductImage.vue及其独立Facade spec两个Feature路径作为旧图片实现的薄兼容去重，
不含其它Feature代码；实体测试不得反向依赖Feature。
Owner封存精确共享SHA/Gate1后，正常no-ff合回原选品Feature，再只在候选池显式启用并交精确试点Candidate。
7d55目前只读准备；候选池紧凑视觉获用户确认、ca97审核精确依赖后，7d55在原分支正常no-ff消费
该纯共享SHA，仅/product-data启用，不merge整条选品Feature、不并改共享。实体add/add冲突必须
采用获批共享版本/接口并保留已有修复，Owner在交接列明冲突路径，不用旧组件覆盖。

验收按两批：

1. 先仅候选池新尺寸。独立检查默认使用方、选品详情/编辑、店铺/经营模块保持原样；被启用筛选的
   teleport下拉自身紧凑，tooltip/其它下拉与跨页默认恢复无泄漏。不用:root改默认、zoom/transform
   或页面复制样式绕过；不为此创建新框架。普通/最大化/必要窄窗只验本次受影响区域。
   Teleport只改变DOM，不退出Vue provide：显式详情/编辑VNode须在密度边界外，或经测试恢复原父主题；
   仅挂到外部OverlayHost不算隔离，不修改抽屉/表单内部作为补救。
2. 用户确认后同Owner接策略列表/工具栏，7d55按批准共享SHA接其页面，再分别验受影响区域。
   商品库/采集任务仍占位，本轮仅登记未来复用规则，不能冒充已改造或借机新增功能。

已实读7d55详情复用默认ProductInfoCell/thumbnail64；它不应被列表48连带改动，也不为统一80而
额外改详情。选品详情summary80照旧。共享阶段不连接数据库/启动Backend，不占新端口/迁移槽，
仅原4176，7d55原4177和Integration8100/5180/0046/唯一Electron/Profile保持，无生产写入或清理。

原真实单商品basic任务始终由ca97负责：必须正常认证→正式basic Run→原队列/Accessor/Signer→
单商品真实请求→字段状态/事实/查询一致，证明saved0且不改rank/video/策略/计划；不能用视觉、
数据库夹具或API拦截替代。当前仍未执行，手动/定时关闭及平台guard保留，整体Gate2/发布不通过。

## 集成迁移与运行版本

复用control_center_integration/control_center_dev_user及既有严格35433连接；未改凭据、Feature或生产。
pre46受保护custom dump为556835字节，pg_restore list343项可读，SHA256
`3185e874ea83c4bc689e7a801323ac5842814d39b72851b225614b6b5ae19d16`。
正式Alembic从候选归档执行45→单一`20261015_0046`，Migration文件SHA256
`F87B00229065BADC506CE3BE38E59AB9E7B2DF1833918941D8F4833F924C2F9C`。
12张原业务表全部旧字段的逐行摘要/计数保持，HuanYu仍valid v6；42–45文件不改。

只停止经PID/命令/监听核对的旧8100/5180服务。新Backend/Frontend实际来自精确51852cc6归档，
8100/5180 strictPort，Real。/health返回ok，OpenAPI正式blocked/basic路由和新Renderer已核对。
本阶段lifespan关闭、手动执行/定时false，并在测试入口阻止选品平台HTTP；非生产Signer8787原配置保留。

## 正式 API 与数据库夹具

通过受保护既有凭据及正常/auth/login建立独立HTTP会话，实际服务端确认g2_sa_v1_super为超级账号，
未注入Token或制造Electron登录状态。场景使用专用G2-CandidateResults A/B（合成验收）、
商品9999000046001001、策略G2-CandidateResults 筛选验收（合成）。
真实Integration数据库和正式API参与，平台适配器是合成响应，实际平台请求0。

| 场景 | 实际结果 |
| --- | --- |
| 全部与今日结果 | 每商品一行，店铺A取最近排名17；不同店铺来源不增加重复商品行 |
| 今日新发现与今日已发现 | 同一商品先新11再已发现17，两类事件均可读，不以最后命中覆盖当天首次事件 |
| 精确批次 | 首次回执排名11、后次17，列表/详情一致；真实回执/canonical可见数量均1 |
| 屏蔽与恢复 | 超级账号无Team头正常操作；全Team商品来源共同隐藏，重复true仅一次审计，恢复可见 |
| 单项基础补充 | 同key回放及活动合并，无重复执行；完成saved0/补充1，不挂策略/计划 |
| 失败与字段缺失 | 合成业务拒绝保留旧值及成功时间；随后真实数值0有效、missing/null保留已有类别和日期 |
| 历史事实 | 基础更新不改rank、video、metric时间、last_run_id或原rank partial/计数 |

首批回执`8709d96d-11f1-48ee-b91a-cbb04134638c`、后批
`20dad5de-3a20-452a-b995-7a8944c020c3`，来源
`b1b9710b-044a-4257-98e5-48274cc2a022`。这些ID仅是本候选集成夹具，不能用于声称平台取数成功。
全部专用Run已终态，原PC/经营/店铺Session数据保持。诊断脚本、JSON、日志、备份、截图及运行PID仅存ignored目录。

## 原生验收与下一步

唯一开发Electron已恢复并加载bfaae14，Real 5180 → 8100 → control_center_integration，单一0046。
用户本次商品信息/首次上榜可见界面确认及此前策略/长名称确认均已记录，范围边界见上节。
此前进程切换曾被工具策略在CreateProcess前拒绝；用户执行正常入口时，
旧脚本又因固定历史PID且窗口已退出而安全拒绝，均未先停止服务。现ignored入口按实际归属判断，
无窗口时正常重开匹配客户端，有窗口时复用；实际新前端进程、已服务模块及现存唯一实例已核对。
这只是本地运行入口修正，不修改候选业务或账号，不删除Profile，不据启动成功宣布整体Gate2通过。
原生截图/坐标输入的既有工具限制保留；本次界面确认依据直接用户消息及附件，不使用网页截图代替，
不将系统剪贴板或两种窗口尺寸的未取证状态改成通过。

真实平台单项样本仍需受控正式队列/当前Integration合法Session与隔离Signer核验；
不复用生产Cookie，不把上述合成数据或历史成功当本候选平台闭环。
只有后续必要验收通过后才正常no-ff合dev、合后复验、精确CI；本轮不自动推进main/生产。
生产3848213119470010668历史业务拒绝的HTTP/st未知与独立click异常继续保留，未被此次准备解决。
