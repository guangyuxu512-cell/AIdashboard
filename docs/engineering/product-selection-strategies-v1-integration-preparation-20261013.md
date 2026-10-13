# 选品策略 A：参数核验与阶段集成准备

状态 **PARTIAL，不是 Gate 2 PASS，不是 Green，不授权跳过未完成验收发布**。

## 当前专项候选：43637bb（团队上下文）

后续精确候选`43637bb051d2f4b3ba6c9fab608756429971edd3`，父c629，已fetch核实。
这是当前实际8100代码；后述77/c629为此前真实证据，不代替新专项原生验收。
新增只有资源Team处理、权限重验及必要测试/文档；Frontend运行代码、Electron、Signer、
Session、日期映射、Model/Migration及PC无差异。ca97独立5个后端文件65项通过。

原问题先以正常人员认证重现：super不发x-team-id，GET两个已有策略200，但PUT/PATCH/
关联获取均409 TEAM_CONTEXT_REQUIRED，版本/状态/Run未变。不是凭开关草稿判定失败阶段。
新版本受控API按正常认证证实：

- 无全局Team、另一有效Team两种上下文，专用实时策略PUT+GET、PATCH启停+GET均200；
  资源Team不改，CAS旧版仍409；完成后保持disabled，版本1经审计更新至7。
- 原正式实时Run同key关联重放202，返回原run，不新执行。新增策略/无关联草稿无Team仍409。
- Run/Schedule/事实增量0，真实观测category/rank/basic_info请求增量均0。
- 不修改当前打开的7d策略（仍v5）或用户尚未保存的类目草稿；不操作普通成员、店铺状态或Session。
  Owner真实PG普通成员、IO后撤权、另一Team等负向证据单列，不能冒称原生。

当前环境是**Integration**：Real5180→8100→control_center_integration，单一20261013_0044。
只正常替换已核实归属且无活动Run的8100后端；5180与唯一Electron不重启/不刷新，
其源码已确认与436相同。Main60592、标题“电商 AI 中控台”、1.0.6与Profile保留。
原生只读成功观察“选品策略”列表及打开的“编辑选品策略”；工具读取Chrome时无法可靠确认地址，
依技能停止本轮输入，未借用其它UI通道。团队专项仍未获得原生点击/人工PASS。
仅请用户置前已有合法HuanYu罗盘短视频页；无需刷新、重新登录或提交Cookie。

原生专项入口“商品中心→选品库→选品策略”，两个专用策略已列明。
保存开关必须以保存后GET为准，获取当前草稿不隐式保存，失败保留抽屉草稿并回读真实列表状态。
已确认结构不重做视觉验收；待工具可安全操作后补专项，不让用户猜版本/去生产尝试。

具体参数缺口仍仅以下四组，不能泛化为“待补证”：1d/30d各自date_type与UI日期范围规则；
known/unknown品牌各自brand_type；custom price_bin编码、元/分及双/单边；其他industry_id与
有序类目路径/父级all前缀。已有确认的7d、实时、默认品牌价格、行业7、官方rank/首次bool不重问。
正常DevTools Query为优先手段，不再重复无法取得Query的页面/Console/performance读取。
若原生Network仍不可读取，已准备本机ignored隐藏输入采集器，仅保留12项业务参数、UI日期、
HTTP及原类型st，丢弃全部签名URL/凭据，无平台请求；它的合成self-test不是平台证据。

B正式最小Schema/事务提案已审核，依真实人类A/B任务分离分支；0045仅reserved，
唯一active仍A0044。B非DDL准备可继续，不等待用户重新发任务；A完整Gate+精确Green后串行激活，
不能把未验B混入A发布。当前A仍PARTIAL，不合dev业务、不推main或发布。

## 先前阶段事实（77a1d96及c629）

当前阶段候选 `77a1d96a2989ada3ef7f12bbba0e0782588468d1`，基线 Green
`3128d6ad1048dfda1240148e863ea0c98eb6247f`。ca97 不代开发业务；81a1继续原Feature，
新条件实现正常产生下一候选，不冻结77。B仍未实现、无新Slot，不等待达人或手机。

## 当前真实集成环境

- 由受信任35433连接到 `control_center_integration` / `control_center_dev_user`。
- 正式Alembic `0043 → 20261013_0044` 已执行；唯一Head已核验，候选代码Head相同。
  新增策略表与run可空关联，迁移前后所有既有业务计数以及HuanYu valid v6相同。
  未在Feature、Main smoke或生产写数据，未修改0042/0043，未执行downgrade。
- 精确候选归档加载至Real `5180 --strictPort → 8100`；已核对进程谱系及源文件Git blob。
  后端健康200。只在本地开启选品手动执行；经营采集/每日经营执行/付费生成仍关闭。
  先以lifespan off验证纯配置，再启用现有正式lifespan及Selection执行器完成指定一次任务。
- 现有Electron源码与Green相同，Profile及人员/店铺会话保留；**本轮没有启动原生窗口，
  没有Electron人工验收**。computer-use无法可靠确认前台Chrome网址后停止本轮原生操作，
  不改用其它低层UI通道；只请用户将既有HuanYu罗盘标签置前，无需换Cookie或重做登录。
- 正常认证核实 `g2_sa_v1_super` 启用且真实超级账号身份。
  旧本机受保护条目返回401；用此前用户授权的固定凭据经正常认证验证后，仅刷新该既有
  Integration条目，密码未写Git/日志/文档，未重置账号或生产密码。
  HTTP测试人员会话不冒称为Electron已登录；现有Profile不清理、不注入Token。

## 已确认映射与立即交接

| 界面选项 | 参数或过滤 | 实际证据/边界 |
| --- | --- | --- |
| 短视频 | 既有video_bring_good路径、rank_data_type=1 | 既有正式样本及本次三个榜单页均HTTP200/int st=0 |
| 近7天 | date_type=21；接受日D冻结D−7～D−1，原批准备用整体前移一天 | 本次正式run实际主区间10-06～10-12，无回退；保留旧有限回退规则 |
| 品牌/价格不限 | brand_type=-1、price_bin=不限 | 本次实际业务Query与已确认旧样本一致 |
| 智能家居/餐饮厨具父级 | industry_id=7、category_id=1000009092,1000009142 | 类目正式Service校验与实际发送；不把行业7塞进category_id |
| 排名21～30 | 现有分页1/2/3、官方rank过滤 | 正式10条的原排名21…30已入库并经API/详情一致核对，不以行号代替 |
| 首次上榜 | 平台newly_on_ranking严格布尔true | 本次10条来源中1 true/9 false/0未知；未把本地first_seen冒充平台标记。过滤分支技术测试与实际标记样本分开 |
| 实时 | date_type=1，上海接受当日begin=end午夜 | 旧用户实时Query及本次10-13当日只读重放HTTP200/int st=0、10条/total200；不是同一次页面新捕获，不外推全天可用或其它周期。已交Owner实现独立单窗口，不继承7d回退 |

脱敏实时业务证据为本机忽略目录
`.codex/gate2-selection-strategies-a-v1/realtime-evidence-20261013.json`；
原人工Query为`.codex/product-selection-query-evidence-20261011.json samples[1].query`。
只保留12项业务参数和状态/计数，没有Cookie、签名、完整URL、请求头或原始响应。

仍未确认，不猜测开放：

- 近1天、近30天各自date_type及准确begin/end规则；
- 知名与非知名各自brand_type；
- 自定义price_bin实际编码、界面金额单位与上下界/单边行为；
- 其它行业实际industry_id、有序category路径及其父级“全部”实际前缀。

Owner已开始补成功PUT编辑、CAS冲突保留草稿的现有前端场景，并接实时映射。
保存/编辑/列表/启停不依赖以上未知值，继续验证，不等待全部参数齐备。

## 正常认证后的配置API验证

专用Integration策略 `G2-Selection-A 保存编辑验收`，ID
`c3a3f9c5-87d3-4265-a7c3-0de8820ea787`，请求HuanYu、近7天21～30、默认品牌/价格。
POST201，PUT编辑及GET刷新200，旧版本409，启停PATCH200；最终disabled/version5。
daily 12:34仅未启用草稿，schedule_available=false、next_run_at=null，未启用B。
这些操作Run/Schedule/事实增量0；测试运行态IO观测category/rank/basic_info均0。
初次测试脚本把省略可选默认值的请求JSON与规范化DTO直接比较而断言失败，随后改为正式schema
规范化对比；业务候选没有因此被修改，不能把脚本迭代当成业务修复。

## 正式真实取数与回读

Run **`dae3090a-ceb4-44f3-8bba-4bbf362a5cbf`**，2026-10-13 08:23:39+08接受。
Integration HuanYu ID `c448f225-b141-409b-bc94-12f1ae74ee04`，平台243321624，合法StoredSession v6。
使用正式POST/现有队列/SelectionRunExecutor/Accessor/DouyinApiClient/本地隔离Signer，
不是诊断响应灌库。主区间2026-10-06～10-12，v3，date_outcome=primary。

- 实际榜单页1/2/3均HTTP200、整数st=0；选中官方21…30共10条，10候选/10来源写入。
- basic_info 9成功、1拒绝：商品 `3828849777110548961`（rank23），HTTP200/整数业务码
  `600002`；安全码 `DOUYIN_SELECTION_BUSINESS_REJECTED`、阶段basic_info_request。
  具体平台原因尚未确定，不把它认定为Session失效/日期未就绪；不重试。
- 正式run如实partial，PRODUCT_SELECTION_BASIC_INFO_INCOMPLETE；该商品及有效榜单指标保留，
  未取得的补充字段为空。数据库、正式候选API及精确详情的ID/排名/实际日期一致。
- 相同提交key重放同Run；完成后刷新GET及再同keyPOST，category/rank/basic_info实际发送增量
  均0。执行不隐式保存，策略version5及原条件不变。
- 总正式IO为category1/rank3/basic_info10；另有此前实时只读诊断rank1，无事实写入，分开记录。
  严格“全部basic_info成功”的测试脚本结果为FORMAL_RUN_INCOMPLETE，后续只读回读确认
  10条持久化与查询一致及9/1真实状态，不把partial倒写成功或冒称全部补充已取得。

当前20候选/20来源/5Run；经营Job19、Item2820、日事实667、PC Schedule3/Run1/Task4、
ShopSession2与初始值一致，HuanYu仍valid v6，活动SelectionRun0。

## 下一动作与发布门槛

1. 81a1交实时及必要验证的新完整阶段Candidate；ca97复核新增JSON读取/旧v1/2/3兼容和不扩回退。
2. 新候选实际加载5180/8100，正常唯一Electron复用既有Profile；明确Candidate/集成环境、
   专用保存策略与真实run范围后，只补新增保存/编辑/启停/实时行为，不重做旧布局视觉。
3. 其它未知选项按最少正常页面Query逐项补证并接线，不能静默丢掉用户选择。
4. 未完项解决并完整Gate2后才no-ff合dev、精确CI Green、Main Release及生产核验。
   新v4若写入须保留最终兼容Backend Reader、0044和全部事实，用原management/execution
   开关恢复只读，不能直接回退77/3128等旧Reader或downgrade清数据。

本记录不代表A已收口或任何生产发布；生产、Main和远端dev本轮未修改。

## 接证后的新精确候选与实际运行（c6298c2）

Owner已交 `c6298c22378fcfc0b4a88e891875f2ae03b1da98`，正常追加77、已推送、工作树干净。
22文件增量主要是实时v4及编辑/CAS测试，Migration/Model/Electron/PC/Signer无差异。
ca97独立后端无DB定向53、前端真实service/run-display18 PASS；旧7d路径与P1/P2未重做。
实际前后端均已换至c629归档，HTTP5180模块含实时policy、Git blob及进程谱系匹配；
8100健康200且capabilities为realtime/7d。本次没有再次迁移。

通过正常认证创建 `G2-Selection-A 实时验收`，ID
`c0c62cee-5bb1-458d-8597-05a4414e0a37`，既有Team
`Electron Gate 2 参数预设验收`（ID 18db2a99-a6ce-439c-94e9-915c15a66e1d）。
saved v1/disabled，保存平台IO0、不生成定时；随后执行当前已保存的实时1–10草稿。

正式run **`5b3d3ba4-4d64-4202-888d-50cf8915eccc`**，09:13:56～09:14:21+08，
Integration HuanYu stored v6、已确认行业/父级路径，HTTP200/int st0。
v4只冻结上海2026-10-13，begin=end、date_type=1、primary，无backup。
真实10条来源事实入库，basic_info10/10成功；DB/API/精确详情ID与当日日期/policy一致，
保存版本仍1。完成后GET刷新及同key重放同Run，category/rank/basic_info增量全0。
实际IO category1/rank1/basic10；不是复用此前只读诊断数据灌库。
旧77 v3 partial run在新Reader回读200、9/1状态/事实保留，未重试业务600002。
总体26候选/30来源/6Run，不能把10条新来源误称10个全新主档；旧经营/PC/Session计数不变。

已通过项目现有正常启动入口重开唯一开发Electron，Main PID60592、窗口标题
**电商 AI 中控台**，版本1.0.6，Profile未清理；Main/Preload源码与c629相同，复用原匹配编译壳，
前后端实际为c629。没有生产客户端或第二个开发Main，没有新安装包/生产操作。
这是程序正常启动和运行态确认，**不是原生截图/点击验收**；computer-use原生操作本轮仍暂停，
尚未读取实际页内账号/入口，不用HTTP认证代替人员视觉确认。

集中人工入口为“商品中心 → 选品库 → 选品策略”，在上述Team检查两个明确策略的
保存/编辑回显/启停、未调度草稿，以及候选池的实时当日详情/刷新；已确认布局不重复验。
不需要再点“立即获取”重复此两次真实任务。其它未知参数仍按前述清单分别补证，
A整体仍PARTIAL，未合dev/未Green/未发布；本段不等待B。
