# 选品策略 A：参数核验与阶段集成准备

状态 **PARTIAL，不是 Gate 2 PASS，不是 Green，不授权跳过未完成验收发布**。

### 凭据恢复后的当前状态（22:31 Asia/Shanghai）

按当前人类条件授权，Main因另一直接人类任务只提供既有正式通道元数据，ca97经DBA入口完成
生产只读关联核查及开发Role运维。生产root配置、实际Backend/Signer均为独立
`control_center_prod_app`，角色/密码不共用；current与三镜像仍精确
`0102dd6d051f89907bad113c35310bbab69412ec`，配置/进程不改，生产health正常。

只轮换`control_center_dev_user`，原角色属性和授权保持。受保护同步81a1、ca97、Main smoke及
额外0106本机连接配置和服务器DEV配置，仅密码变化。三处新鲜连接PASS、旧密码明确认证拒绝，
主要业务计数和Integration单一0044保留；Main smoke实际旧Head0034只记录，不因凭据处理升级。
0106残留配置指向已不存在的旧Feature库，密码已同步但不重建；服务器DEV Backend保持停止，
停止容器存有失效旧环境，未来启用必须正式Compose重载而不是直接docker start。

首轮受保护文件准备的ACL格式错误发生在远程操作前，只有空文件，核对后移除并定向修正，
实际Role只轮换一次。后续完整连接检查唯一额外失败为0106旧库不存在，不反复换密码掩盖。
原工具输出仅按事件标识做流式计数，未导出内容；无历史编辑接口，旧失效值仍留存，不能声称
已删除或全历史脱敏。新密码不进入聊天/日志/Git；本机配置限定当前Windows用户与SYSTEM。
加密临时恢复材料已撤除，保留非敏感审计。

只回收归属核实且无活动任务的8100 Backend以加载新配置；当前84500/health200，5180/54832及
唯一Electron98292/Profile保留，实际仍8df。安全hold解除；Owner正在新56b补真实Feature PG，
之后才匹配加载并验证既有run的精确GET，无需重复取榜或未变视觉。A整体仍PARTIAL。

### 恢复后的读取团队尾部验收

Owner最终测试/文档补充Candidate `183b35b4057b979f21a15e117cb2d3e8ef3b9efc`，父56b，
已推送且运行时代码与56b完全相同；ca97已回读实际差异与Gate1记录。新增真实PG权限交错
canonical/reused两例通过，最终五文件PG96/213.37s；默认636/66.80s、纯逻辑59独立记录。
首轮93pass/1fail并发断言过严的问题保留，不以重跑掩盖。现契约只保证全局一个running与
回执不领取，SKIP LOCKED不承诺并发严格FIFO；测试修正并新增无锁串行/锁首条跳过两例，
领取算法、索引及优先级不变。详见Owner团队上下文Gate1文档。

ca97归档并实际加载183 Backend（PID91792/8100/health200），单一0044及旧业务计数保留；
保留5180/54832的8df前端源码，其全部Frontend字节与183相同，Electron源码也相同，
唯一原窗口98292和Profile不动，不用分支HEAD冒充原生新视觉。
通过正常认证回读原v4正式run `5b3d3ba4-4d64-4202-888d-50cf8915eccc`：
原Team、无Team、另一有效Team同Header均同keyPOST202→精确GET200且DTO一致。
Run/Schedule/事实以及category/rank/basic_info请求增量全0，未重取榜或造新数据。
原8df另一Team GET404定向缺口关闭；PG交错与正式HTTP是不同证据，不冒称全A Gate2B通过。
用户原生行序/分页/筛选/滚动未确认项及未知参数继续原边界，未合dev业务、未标Green或发布。

### 晚间安全hold与新交审候选（已解除的历史记录）

Owner先交审 `ed6a98b95b74ca5f2dd29df0e926fdf1db577bd1`、父8df，已push、Owner干净；
随后定向返修`56b9614235708faf86bb237c27dffaf8b8ae6165`、父ed6已push，当前以56b交审。
唯一runtime变化是精确Run GET派生已存Team，Frontend/Electron/0042/3/4与8df无差异；
当前两个服务/唯一Electron仍8df，未加载ed6，不把新的HEAD冒充实际运行。

ca97在实际8df，仅同key重放既有正式run `5b3d3ba4-4d64-4202-888d-50cf8915eccc`：
原Team、无Team各POST202→GET200；另一有效Team POST202→GET404/PRODUCT_SELECTION_RUN_NOT_FOUND。
均指向同一原run，Run/Schedule/事实/category/rank/basic_info增量0，没有新请求或改策略/Profile。
ed6技术审查的无DB原方法交错探针发现：第一次super全局精确查询后，第二次权威身份变成无Shop
grant的普通成员，非reused row直接_read返回，未在最终Actor下再次走已有Repo可见性查询。
已交原Owner做最小fail-closed返修，Integrator不代修。此证据仅method-only合成，不称PG/平台。
Owner已完成92 PG/630默认是此前版本的真实执行记录，不覆盖该新增交错；无新增Migration。
56b仅加最终权威Actor下的第二次精确Repo可见查询，None继续原NotFound；没有新权限框架。
ca97同一原方法无配置/无DB交错探针确认：查询2次、最终Actor下1次，无授权row不返回。
这是定向技术修补接受，不是新PG/正式API或全A通过；Owner6项与连既有纯逻辑59项为无DB自检，
父ed6的92PG/630默认只作父版本事实。Frontend/Electron/Migration仍与8df相同，待安全核销后补
新候选PG和同Header真实旧run精确GET，不重复取榜/未变视觉；当前仍未加载56b。

随后Owner额外只读探针因PostgresDsn对象类型错误，异常工具输出暴露Feature连接凭据。
Owner已停止使用；没有把该失败当Head/计数核验成功。ca97不读取/复制含敏感值的原异常，
仅内存解析三个已登记配置：Feature control_center_feat_product_selection、Integration
control_center_integration、Main smoke control_center_dev，共用同端点/control_center_dev_user及密码。
生产配置未读取，关系UNKNOWN；ed6变更内容旧敏感值匹配数0，不能把此有限扫描称全库或日志无泄露。

尚未轮换Role、未改三处配置或生产；按本地Integration写入边界及该Role无CREATEROLE的既有事实，
须对应Main/DB管理员先只读确认生产关联，在明确授权范围内受保护轮换并同步相关非生产配置，
若涉及生产则先明确影响，不自行扩授权。主动DB验证/发布hold；ignored controller在配置加载/连接前
拒绝，原唯一窗口/Profile/人员和平台会话保留。安全核销后才恢复定向PG/正式API及Gate流程。

参数侧仍可无DB推进：已正常定位既有HuanYu罗盘短视频页的个护家清父级菜单；当前只有DOM/
pageAssets，Network Query不可读，原生Chrome主窗未匹配该后台罗盘标签。正常菜单操作已使界面选择
变成个护家清/个人护理，但未取得对应请求参数，不将此截图当映射已证实。已具体请用户仅一次
个护家清/家清纸品/全部的12业务Query、HTTP/st及UI日期，或本机隐藏输入安全采集；不索Cookie/cURL。
本机入口实检READY，空category原样保留不推断、仅12业务字段、认证字段保留0、脚本请求0。

## 当前专项候选：8df（列表稳定）

精确Candidate `8dfb2dcf217b9883e9cd2ddbac9a02da8ee33fc3`、父436，Owner干净已推送。
2026-10-13晚间用户正常启动后，Backend/Frontend已启动，只有助手ReadAllLines读取正在写入的
重定向日志发生共享冲突；不是Backend失败。ca97只修ignored启动助手为FileShare.ReadWrite/Delete
只读，并按真实监听/父进程核实复用8100/5180；没有停止服务、改业务代码、安装依赖或再次迁移。

实际8100/5180 HTTP200，Vite模块含updateSavedRow/onBeforeUnmount，白名单Backend启动事件精确8df。
正常原入口打开唯一匹配1.0.6开发Electron，Main/Preload源码与8df相同、原Profile保留；
真实原生AX读取`http://127.0.0.1:5180/#/shops`、G2-SA-V1 Super Account，无需重新登录。
截图捕获FrameArrived超时，重选后AX可读，但点击报coordinate input geometry unavailable；
不借用其它UI技术绕过，不把网页截图或浏览器拦截测试当原生确认。

正常认证后的正式API已验证启用/停用/编辑及恢复原名：稳定created_at DESC/ID ASC顺序、
固定API第二页（page_size=1）/名称筛选保持，真正updated_at与version更新、最近真实结果不变。
目标实时策略最终v15/disabled；原7d已保存记录完全不变。Run/计划/候选/来源及category/rank/basic_info
增量全部0；API固定分页不是原生分页/滚动证据。

再经正式API准备37条`G2-Selection-A 原生稳定页配置 01…37`，全部disabled/unscheduled、
无latest_run/next_run_at。加原3条共40条，搜索`G2-Selection-A`、20/页时第二页完整20行，
靠下目标`G2-Selection-A 实时验收`（ID c0c62cee-5bb1-458d-8597-05a4414e0a37）可检查横纵滚动。
仅新增配置，不是模拟榜单/平台事实；准备前后Run/计划/事实/平台请求仍0增量。稳定ID清单在本机ignored
证据中保留，没有策略DELETE契约，未经明确清理不编造接口或删除其它记录。

用户仅需在同一集成Electron进行此目标启停/编辑保存，核实行序、第二页、搜索、滚动及状态原位更新；
不点立即获取、不重复旧视觉。收到原生确认前Gate2B未通过。参数缺口仍是下述精确四组，
ca97补证一项即交81a1实现，0044 active/0045 reserved及7d55不参与不变；未合dev业务/未发布。

## 43637bb团队上下文证据（历史阶段）

后续精确候选`43637bb051d2f4b3ba6c9fab608756429971edd3`，父c629，已fetch核实。
这是此前实际8100代码，当前已更新8df；本段及后述77/c629真实证据保留，不代替新专项原生验收。
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

### 独立B非DDL准备审查（不改变A运行）

Owner已推送`f4f61c926d40193b5a5d939927f967f6fee42068`，父beaf7ce，分支B，
正常包含A436依赖，不是完整B或A Release目标。ca97只在独立ignored源码归档审查和运行测试：
时间规则/PC service/scanner与选品mapping/realtime/strategy/source/connector共8文件91 pass，
无DB/平台调用；diff check通过。未替换现有A marker/前后端/Electron或其Profile/草稿。

审核接受的准备是：上海整点next严格未来、latest含到点；原submit负责权限/类目/CAS和外层
commit/rollback，抽取的私有persist只使用原savepoint/唯一冲突处理；策略活动查询同时检查
canonical pending/running、双Team、Shop和fingerprint，包含该策略复用另一/无关联canonical，
终态不永久占用。未来Due Service仍须完整授权与持策略/发生时刻锁后使用，不是新增授权入口。
Model、Migration、Schedule DTO、Scanner、Settings、Frontend、Electron和Worker无变更。

OwnerPG90为登记Feature真实数据库/合成I/O，与ca9791项不累加为某个完整Gate数字。
未验证真实到点、关闭Electron/Worker离线或新Schema，不称B可运行。0045仍reserved，
唯一active A0044；A具体参数取证和原生专项继续，不以B准备结果替代或阻塞A。

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

## 8df列表稳定返修：早先运行未恢复的历史停点

2026-10-13用户明确继续A；Candidate `8dfb2dcf217b9883e9cd2ddbac9a02da8ee33fc3`，
父43637bb，Owner工作树干净且已推送。仅稳定created_at DESC/strategy_id ASC及原位Query更新，
已有编辑不再无条件回第一页；真实updated_at/CAS/权限保留，布局与取数规则不重做。
ca97已准备精确source-8dfb2dc归档，3个运行修改文件与Git blob一致；独立List/Drawer14项通过。
Migration/Electron/Signer/mapper/executor相对436无变化，既有浏览器证据仅为技术证据。

正常重开Codex后，旧8100/5180及开发Electron已不存在，不能把旧436运行记录当新候选已加载。
ca97恢复了严格主机公钥校验的既有35433隧道；只读实检Integration单一0044、26候选/30来源/6run、
活动run0、HuanYu valid v6保留，既有隔离Signer8787健康HTTP200；未迁移、未写业务表、未请求平台。
原生工具因不能可靠核实前台Chrome网址停止本轮窗口输入；extension只提供viewport/pageAssets，
没有Network读取，不再用DOM/控制台重复冒充Query补证。仅请用户置前现有HuanYu罗盘短视频榜。

正常前后端Start-Process组合在CreateProcess前被工具策略拒绝，实际8100/5180仍未监听，
Electron未运行、未加载8df；不是生产客户端未关闭或业务启动错误。未换方法绕过拒绝。
本机ignored `resume-reviewed-runtime-8dfb2dc.ps1`已准备，静态语法0错误；用户一次正常执行后，
ca97核对实际进程、HTTP模块与backend白名单启动标记，再由原入口恢复唯一匹配1.0.6壳及原Profile。
此准备文件或匹配源码不是原生验收；尚未标Gate2B PASS。

当前专用策略仅3条，第二页原生专项尚需通过正式API补足disabled配置，不能让用户自行排查夹具。
恢复后检查启停/编辑前后的行ID顺序、当前页、名称筛选、横纵滚动、版本/最近结果及零新增Run/平台请求；
原已确认页面结构和既有真实7d/实时run直接复用，不为位置修复重复获取榜单。

剩余缺口具体为：其它行业industry_id/有序category_id及父级全部实际前缀；1d/30d各自date_type、
begin/end与页面日期含义；known/unknown各自brand_type；custom价格字段格式、元/分、上下界/单边规则。
ca97确认一项即交81a1同步mapper/契约/capabilities/Real service/保存回显及定向测试，不等整套。
A完整Gate/Green后交Main发布；B仍独立非DDL准备，0044 active/0045 reserved按原顺序，不把计划保存当自动执行。
