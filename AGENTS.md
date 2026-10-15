# AGENTS.md

## 0. 工程工作流总则（Two-Gate）

本文件同时是仓库工程治理的最高规则；模块 `AGENTS.md` 只保留各自的技术边界，并引用本节。完整操作流程、环境登记与数据库协作细则见：

- `docs/engineering/01-开发集成与发布流程.md`
- `docs/engineering/02-工程环境与工作树登记表.md`
- `docs/engineering/03-数据库与Migration协作规范.md`

### Branch 与 Worktree 角色

- `main` 仅保存已发布或已确认稳定的版本；只能由通过 Release Gate 的 Green `dev` 合入。
- `dev` 是唯一集成线，也是 Green `dev` 的唯一来源；Feature 只能通过 Integration Worktree 按 `--no-ff` 合入。
- 新业务在 `feat/*`，紧急线上修复在 `hotfix/*`；不得建立长期 `qa/*`、`test/*`、`review/*` 等平行集成线。
- 新 Feature 从最新 Green `dev` 创建，且一个 Worktree 只绑定一个分支。已有 AI、Mobile 长期分支按登记表保留，不因本规则补做 rebase、重建或改名。
- 当前工作树中的 `AGENTS.md` 和 `docs/` 才是该分支的规则快照；禁止把其他 Worktree 的文件当作当前分支事实。

2026-10-13 7d55已正规恢复为“可用功能开发工作树，具体任务待分配”：
主仓库Git以CI成功的Green `3128d6ad1048dfda1240148e863ea0c98eb6247f`创建原路径
`C:\Users\Administrator\.codex\worktrees\7d55\中控台`，当前detached HEAD、源码与规则完整且工作区干净。
旧残留目录完整改名保留于 `C:\Users\Administrator\.codex\worktrees\7d55-archive-20261013-1baaab5b`；
经用户授权归档旧7d55聊天并正常重开Codex后，目录占用解除，未强杀或改ACL。
本次不分配数据库、端口或Migration Slot，不启动/打包Electron，不动81a1共享stash或既有Profile。
确定新功能后再从当时核验的最新Green建对应分支、登记所需资源；不继承旧“仅打包”职责。

### Two-Gate、问题归属与共享历史

2026-10-15当前实际前端预览为完整Candidate `610922781f1eec01e493122f8c1a3a50558e5bce`，
正常no-ff消费纯共享1a8078（merge7e37c6b，父b99与1a），运行仅全局AppTable竖线及候选池
局部商品列280–300px/标题约199–219px，原居中及局部紧凑不变。ca97独立11项/lint/typecheck/
精确Real build18.17秒和11份blob通过，复用纯共享23项及未变证据。5180已实际切换并回读新模块，
8100/唯一1.0.6 Electron/Profile保留；原35433隧道退出，已按既有严格host-key入口恢复，只读
确认单一0046/29候选/旧计数及HuanYu valid v6。原生AX可读、同一窗口已置前，停在策略Tab；
点击缺geometry且键盘切换未确认，不以源码/Mock图冒充新布局原生PASS，只交用户集中补确认。
新布局与全局线未获实际确认前不放行7d55/策略密度、不合业务、不发布；真实basic Gate仍独立。

2026-10-15新增直接人类设计授权已由ca97回读规划turn
`01a13e0d-f1df-7cb1-977d-70262e09218c`：标题缩短、居中沿用原规则、全局列表表格加竖线。
本条覆盖此前仅商品表格竖线opt-in的讨论，但不把12px/28px/48px紧凑密度扩成全局默认。
81a1仍唯一共享Owner；纯共享分支从6ac追加现成AppTable竖线及必要可选商品信息能力，
不得带0046业务，随后正常no-ff合回原b99候选池Feature调整标题/列宽。7d55等新精确依赖及
实际候选池视觉确认后再消费，不能先拿旧6ac。原list居中/grid语义与详情已有边框保持，
不换生成图数据、不加双线或重写列宽框架。当前b99同一窗口/Profile/0046保留；新候选待交。
设计选择不是新原生验收、全Gate或发布授权；真实basic Gate独立、不清理Mock、不操作生产。

2026-10-15候选池当前精确Candidate为`bfaae14d76780f031e34ef68b139a26bb19b8694`，
父9734809复用共享商品信息，继承f876长标签及原功能；新增首次上榜只读列，直接复用
newly_on_ranking/firstListed的真/假/未知，不推算或新增排序筛选。ca97独立增量18项、lint/typecheck/
Real build通过，复用973的140项及未变证据；Backend/Electron/依赖/0046不变。
同一Real5180/8100、唯一1.0.6/Profile及29条数据保留。已回读规划人类
turn01a13db6-ba41-7520-86f3-4f65d62a9fc2的“验收没问题”及对应截图，登记商品信息和首次上榜
可见界面确认；原生系统剪贴板结果、普通/最大化专项未单独取证，不补写通过或重复整体界面验收。
真实单商品basic正式Run仍未执行，Gate2整体进行中、0046唯一active；未合dev业务、无新Green或
本Feature生产授权。此前字体/控件密度的只读评估限制已被下面新增直接人类授权替代；
原bfaae界面确认保留，不视为新紧凑尺寸确认，不启动残留清理。
具体证据见候选池Gate2文档；本条更新最新状态，以下f876等记录作为阶段证据保留。

2026-10-15紧凑列表已获规划人类turn01a13dba-08ad-7992-977b-42350767e6a3批准。
81a1唯一共享Owner，同一工作树串行从CI成功Green9bb64ac新建纯前端
`feat/compact-product-list-foundation-v1`，原bfaae分支/已验成果保留，不回退或改写历史。
共享分支仅显式compact Primitive/列表模式/商品实体及必要ShopSelector透传、测试/契约，默认不变；
不得合入选品0046业务或7d55全模块。封存精确共享SHA后，Owner正常no-ff合回原选品Feature，
仅候选池先行；ca97独立Gate2/同一Real Electron确认新视觉后，才推进策略列表及7d55页面消费。
7d55在原b364分支只读准备，获精确依赖及用户确认后正常no-ff消费纯共享SHA，不并改共享文件。
表头/列表/ID12px、筛选标签13px、控件28px/文字12px、筛选gap8px、卡片padding12px、列表图48px，
行高目标约64px但不裁内容；分页/批量栏显式匹配。默认字体/家族/导航/主题/圆角与详情/表单不改，
summary80/默认thumbnail64保持，teleport和跨页恢复必须验。商品库/采集任务占位只登记规则。
无新DB/Slot/端口/第二Electron；共享阶段不连DB，原0046仍仅候选池Featureactive。
本地治理提交不是Green，真实单项basic闭环仍由ca97负责；新视觉未确认前不合功能、不发布。

2026-10-15候选池阶段Candidate为`f876f83ec558766617ed2b07ccf87f213d2493cf`，
直接父51852。共享AppSelect/ShopSelector复用NTooltip的长标签opt-in返修独立134项、lint/typecheck/
Real build通过，Backend/Electron/依赖/0046不变。5180已实际加载f876，8100父51852源码逐字相同；
唯一匹配1.0.6开发Electron/Profile保留。用户直接确认“刚才说的策略，界面。都验收通过”，
登记本次策略界面与长名称悬浮人工通过，不重复要求这部分操作。
Owner81a1从Green9bb64ac独立开发并完成Gate1。ca97独立技术、Backend默认807项/Frontend124项、
lint/typecheck/Real build及正式认证Integration API验证通过；受保护备份可读后正式升级Integration
单一0046，12表旧字段逐行摘要与HuanYu valid v6保持。8100/5180 strictPort已加载精确候选，
此前原生窗口恢复与固定PID入口问题已通过正常准备入口处理，不启动第二实例或重置登录。
专用G2-CandidateResults为合成平台+真实Integration数据库/API证据，实际平台请求0，
不是本候选真实平台成功；真实单项基础更新仍待核验，整体Gate2尚未通过。
0046仍唯一active/down45，42–45字节不改；无dev业务合并、
新Green或本Feature生产授权。生产保持B382/0045；7d55独立4177不混入。
详见候选池Gate2记录，ca97治理HEAD不代替Green9bb或授权发布。

2026-10-15新增资源：规划人类已确认并正式分配7d55商品数据前端第一阶段，Owner从精确Green
9bb64ac正常建立feat/shop-product-data-frontend-v1（现场旧detached3128干净，禁止旧基线编码）。
仅前端Mock/契约只读盘点，独立4177 strictPort，无DB/Backend/Signer/Migration/第二Electron；
不占81a1的8101/4176及Integration8100/5180，不混候选池修复或B发布。保留Profile/stash/归档，
新Candidate Gate1后ca97受控预览，人工确认前不合dev或发布；资源文档为当前放行，不是Gate。

2026-10-15 B正式收口：精确Green9bb64ac76bf9e0f51fb1715517cf8c18cef63e22经Main正常no-ff
Release为`382ca92ee1f415e0e1a4269de6b9a02c382e114d`；main CI38599163540和正式
Deploy38599686878 attempt1全部success，实际三服务/current同382、单一0045、健康/Real资产通过。
新鲜pre45备份可读、11表旧字段逐行保留；生产持久定时开关及实际getterexecution/management/
schedule全true、并发3，原经营09:00仅昨日保持。生产选品尚0策略/Run，不复制Integration夹具或
冒称生产到点实测；已完成真实Integration/关闭客户端及直接人工证据复用，不追加取数。
0045 released/无active，实际1.0.6/Profile及Integration执行false保持；临时跟进已核销。
ca97只读复核/记录，无生产写入；详细证据见B Gate2文档，后续治理不是新Green且不再自动部署。

2026-10-15最新Green为`9bb64ac76bf9e0f51fb1715517cf8c18cef63e22`，B精确7db正常no-ff
合dev89b8d9f，合后复验/直接人类确认及CI38597874343三项success均通过。0045正式released，
无active Slot；Main已获B发布授权，必须用精确Green9bb而非后续纯治理HEAD合main/CI/正式部署。
生产此时仍A103/0044；最终部署/45/健康/开关核验由Main负责，不以Green或交接冒称DEPLOYED。
本条替代下列待CI/Slot active及af57最新Green的阶段结论；无额外功能/平台请求/原生复验。

2026-10-15当前B状态：完整候选`7db6578e67225efe8b77830712ccdbc72d6803cb`的技术、
Integration0045/正式API/真实自然到点（含客户端完全退出）及同一原生Electron验收均通过。
新独立每日配置只供新增控件验收，旧N3/hourly6及真实历史保留；用户已直接回复“验收通过”并
明确授权“继续合并、CI及B发布”。ca97须正常no-ff合dev、复验及精确CI，Main据Green执行Release，
不提前标Green/DEPLOYED或重复验收A；0045至Green核销前仍active。A已正式部署
`103b1c80b82f5bfca78467b887d7fafbdeb1ab60`/单一0044，最小builder修复及09:00原配置保持。
下文旧B待确认/A未部署为阶段历史，不覆盖此当前状态；候选业务及已应用迁移不改。

2026-10-14 人类已直接授权A部署的最小builder入口工程返修，不改业务/依赖/Migration。
唯一Owner81a1在`feat/production-buildx-builder-selection-v1`从A Green f5正常起分支并同步
新确认治理Green `07f1cc79bb4f72776a71eddad527faef0d46016f`（精确CI38511410020三项success，
相对f5运行/迁移/依赖不变）；无DB、端口、服务或Migration Slot。ca97独立Gate2/精确CI后
交Main仅发布A+必要工程修复，不能代修main/dev或混B0045。7d55只读盘点未分配/未改。
B7db候选、已应用45与运行/Profile保留，Owner串行Ops不连接旧Feature库写入。
工程1677 Gate1/独立Gate2已通过，正常no-ff新Green
`af57cc3258cc4e1ab4582db57b9852956ef433f5`精确CI38547082755三项success，已交Main连续A发布。
该提交代码Head0044、相对A业务/依赖/迁移/Electron不变且不含B7db；是最新Green，
下文f5/07为已保留基线，后续纯记录提交不能取代af57。生产DEPLOYED须等Main实际核验，不据CI宣称。

2026-10-14 B当前集成状态：完整候选`7db6578e67225efe8b77830712ccdbc72d6803cb`
独立技术审查接受，已受保护备份并正式升级Integration单一0045，原PC/A/经营/Session逐行保留。
唯一Real5180/8100匹配此候选及同一Electron/Profile；正式API配置/启停零Run、零平台请求通过。
仅专用G2-B在北京时间13:54经原扫描自然触发，真实Run成功保存/补充各1、DB/API一致；
停用/后续扫描无重复，再恢复Integration自动开关关闭。后续正常退出原Electron后，17:11原scanner
再次真实成功、保存补充各1/DB/API一致，开发主进程及PC Worker均0，独立性现场通过；
同一1.0.6/Profile/g2人员会话已恢复，B新增N/daily/下次时间/最近结果的集中原生确认尚待用户。
B Gate2仍进行中，不合dev/main，不冒称部署。该状态替代下文“B未集成/Integration0044”的阶段记录。
A已Green/main CI成功，但首次生产Deploy因Docker daemon panic/status-stream EOF失败，
旧生产0102/0043及09:00原配置健康恢复；A未部署。最小builder范围已获上述直接人类授权，
Owner1677fd3 Draft PR13/Ubuntu CI验证中，Gate1尚未放行，不能按Draft或治理提交发布。
具体B证据与边界见`docs/engineering/product-selection-server-schedule-v1-gate2-20261014.md`。

2026-10-14 B依赖登记历史（保留Owner交接，当前状态以上述10月15日确认优先）：ca97正式确认A精确Green
`f5d4866459acf3e29459a9920c03c1e9118a8839`及CI38503895984全部成功、用户普通/最大化确认。
Owner保留78e06d8及原A，正常no-ff同步该Green，不以治理HEAD代替功能基线。
ca97已串行释放A0044，激活唯一B `20261013_0045_product_selection_server_schedule_v1`，
revision0045/down0044。按已审核最小Schema/事务/隔离队列方案实施完整B，仅使用已登记Feature库，
不改42/43/44，不新增表/队列/第二调度器，不写Integration/生产、不另开Electron。
每N小时、PC隔离、默认全局3/同店及有效策略1、持久排队/租约、自然触发须分别验证；
准备测试不代表B闭环。A已交Main独立发布不等B；平台/唯一Real Electron仍仅ca97协调。
本阶段覆盖下方旧reserved/准备限制；旧证据和未验证事实完整保留。

2026-10-14 当前A收口：精确候选 `f348565b4db2cb907d9c55c3fd7c85088a1fe467` 已完成
逐项契约、实际Real5180/8100匹配验证，Integration单一0044及唯一1.0.6 Electron/Profile保留。
用户已直接确认品牌/策略九列/启停编辑位置，以及最后候选池普通/最大化显示；不重复原生验收。
正式v8 run `e8221905-d2a2-485e-821f-c1465cd0366a` 冻结pages[1,15]，只请求一次page1及15，
官方rank150一条真实事实/basic_info/API一致；品牌0/1正式结果与旧v1–v7证据分开复用。
已正常no-ff合入dev `f5d4866459acf3e29459a9920c03c1e9118a8839`，合后复验通过；
精确CI `38503895984` 的Backend/Real build/container三项成功，该提交为最新Green，已交Main发布A。
A不接入服务端调度；现核销A0044为released，并串行激活B0045/down0044，唯一active为B。
B从精确Green f5d4866正常merge，仍只在登记Feature库实施Model/Migration/PG，未部署或集成B。
B槽位治理提交不是新Green，不将其或未验B代码混入此次A Release；具体范围以Migration登记为准。
同日B首Feature升级约束命名不匹配曾安全回滚/返修占位，Owner只修未应用45后正常升级。
ca97独立只读核实Feature单一0045、八项业务计数0/最小角色，恢复45 active；不冒称B Gate。
Integration仍0044、A生产发布独立，B自然执行/容量/PC数据兼容须继续实现与验证。
已存在v8事实，回退须保留兼容Reader、Schema、历史及审计，不能直接回旧版本或降级清数据。
以下A PARTIAL/旧端口PID为阶段历史，不覆盖本次直接人工确认和实际运行核验；
最终证据与发布边界见 `docs/engineering/product-selection-strategies-v1-gate2-20261014.md`。

历史阶段记录：
2026-10-13 选品后续人类任务已在81a1会话回读：A为罗盘条件补齐与策略保存管理，
B为复用既有Schedule底座的服务端选品，各自Candidate/Gate/发布；不混入达人、百应或手机能力。
81a1从精确Green `3128d6ad1048dfda1240148e863ea0c98eb6247f` 创建
`feat/product-selection-strategies-v1`，保留已发布选品/登录与全部旧分支；对应main及最后实检生产
`0102dd6d051f89907bad113c35310bbab69412ec`。登录当前带Team真实生产路径已通过，
空Team生产样本未覆盖事实独立保留，不作为此次选品任务阻塞，不能倒写PASS。
ca97仅恢复受信任35433隧道并只读核实 retained `control_center_feat_product_selection`、
`control_center_dev_user`、单一0043、候选/观察/run/ShopSession均0、无数据库管理权限；
Feature继续8101/4176 strictPort，Integration仍8100/5180及唯一开发Electron，不复制生产Cookie。
A唯一Slot active（77a1阶段边界修补已复核，未完成Gate）：`20261013_0044_product_selection_strategies_v1`，revision
`20261013_0044`，down `20261010_0043`；一张Team-owned策略表及run可空策略关联，
版本CAS、白名单相对条件/定时草稿，保存/启停本身不取数、不创建Schedule。
0042/0043不改写；未知平台参数不猜测开放。新条件保持旧run/事实读取与指纹兼容，
降级仅可重建Feature且无新策略或关联run，须加锁后检查；应用回退保留Schema/历史。
Owner编写/验证新Migration与代码，ca97不代修；B未分配Slot、不在A接入执行或新建调度框架。
Owner已在分配Feature库应用0044，ca97只读核实该库单一`20261013_0044`与最小角色；
Integration/生产仍0043，未在本工作树新增Migration或写Feature业务数据，实际Gate验证尚待候选。
本记录仅资源与技术边界登记，不代表A实现、Gate或真实平台验收已经通过。
阶段候选`4e584cb993a1a6b22204421018a3cc75d9fa5f0d`已退回Owner：0044实际downgrade缺少
目标Feature库保护（只有测试包装器检查），隔离无连接探针确认能进入mock drop；策略停用还误用
旧停用Shop的执行资格校验，配置无法关闭。Slot按迁移拒绝规则保留待修，不改已应用旧迁移或清库。
隔离快照53后端定向、92前端选品、lint/typecheck/Real build通过不抵消上述缺口；
未加载Integration、未合dev、未发布。Owner修正后交新精确候选重新审查，平台补证仍独立待完成。
追加候选`77a1d96a2989ada3ef7f12bbba0e0782588468d1`独立复核：实际降级在锁/DDL前拒绝
offline及非指定Feature目标；停用Shop的配置可关闭或替换合法新目标，开启/执行仍查资格，CAS/范围不放宽。
8迁移与6配置无连接合成探针及后端定向62项通过；0044 upgrade函数不变，前端/Electron/Signer/PC/0042/3
无差异复用原92项/lint/typecheck/Real build，不重复视觉。Slot恢复active仅表示修补边界接受；
未加载Integration或迁移，不合dev/main，A未知参数与真实闭环仍PARTIAL，B无Slot/实现。

2026-10-13后续人类明确继续A，ca97已将77阶段归档匹配加载Real5180/8100，正式Alembic升级
Integration至单一`20261013_0044`，迁移前后旧事实/run/HuanYu valid v6保留。正常认证配置CRUD/
CAS/启停通过且Run/Schedule/平台IO增量0；正式run `dae3090a-ceb4-44f3-8bba-4bbf362a5cbf`
取得官方21–30、主区间10-06～10-12，10条事实/API/详情一致，basic_info9成功/1业务600002拒绝，
partial如实保留。完成后GET与同key重放平台IO增量0。另按旧人工Query仅一次当日实时只读重放
HTTP200/int0/10条，交Owner接独立当日窗口；不是正式实时入库，不扩7d回退。
原生computer-use因无法确认前台Chrome网址停止本轮操作，未启动/验收Electron；仅请用户置前既有
罗盘标签。其它周期/品牌/自定义价格/行业映射仍具体补证中，A/B未完成，不合dev/main、不标Green。
详见`docs/engineering/product-selection-strategies-v1-integration-preparation-20261013.md`。

同日实时接证候选`c6298c22378fcfc0b4a88e891875f2ae03b1da98`已独立53后端/18前端定向并
匹配加载两服务。正式v4 run `5b3d3ba4-4d64-4202-888d-50cf8915eccc` 当日10条入库、basic10成功、
API/详情一致、同key/刷新IO0；旧v3/9+1partial保留。现26候选/30来源/6run，0044不再修改，
现有1.0.6壳源码相同，按正常项目入口重开唯一开发Main60592且保留Profile，非原生操作通过。
其它参数与人员原生确认仍待完成，不以此标全A Gate/Green或发布；B仍无Slot/实现。

2026-10-13后续A团队上下文候选`43637bb051d2f4b3ba6c9fab608756429971edd3`已独立审查、
65后端定向通过并加载8100；5180/唯一1.0.6 Electron源码与该候选相同，保留当前未保存7d抽屉。
正式API证实super无Team及另一有效Team均可按资源原Team保存/启停/GET和重放已有关联Run；
CAS、新建/无关联草稿必须明确Team的门禁保留，Run/Schedule/事实/平台请求增量0。
这是受控API，非原生点击通过；Chrome地址安全校验停止输入，仅请用户置前现有合法罗盘页，
不换低层UI入口，不重新索要Cookie。未知1d/30d、品牌、自定义价格和其它行业参数仍具体补证。
已回读81a1人类turn `01a13382-b40f-7552-a6a0-a32a6ec092d2`的A/B授权；B独立
`feat/product-selection-server-schedule-v1`从Green3128正常合436依赖，不混A Release。
技术提案已审核，下一Slot`20261013_0045`/down0044仅reserved；A0044仍唯一active，
A完整Gate及精确Green后才串行激活B，此前不写或应用B DDL。详见阶段集成记录与Slot表。

同日B非DDL准备`f4f61c926d40193b5a5d939927f967f6fee42068`已fetch/技术审查接受，
隔离归档91项时间/PC/选品定向通过；无Model/Migration/Scanner/Settings/Frontend/Electron变化。
整点辅助、调用者事务所有权及包含reused的策略活动查询只是准备，不是定时Gate或发布候选。
OwnerPG90为Feature真实DB/合成I/O，ca97未写Feature、未在Integration加载B，0045仍reserved。

同日用户接续A，列表返修Candidate `8dfb2dcf217b9883e9cd2ddbac9a02da8ee33fc3`已独立审查，
List/Drawer14项通过、无迁移/壳/执行规则变化，精确归档已准备。早先正常启动曾在CreateProcess前
被工具策略拒绝；用户随后正常运行启动文件，8100/5180成功启动，但本地助手ReadAllLines读取写入中
日志报文件共享冲突。ca97仅修ignored助手的共享只读与监听归属复用，不改Feature业务或停健康服务。
两服务HTTP200及8df运行字节/白名单启动标记已核实；正常入口已开唯一匹配1.0.6 Electron，
原生AX确认5180/#/shops、G2-SA-V1 Super Account及原Profile保留。截图FrameArrived超时、点击无geometry，
不以网页验收替代原生。正式API启停/编辑保持行序/固定页/筛选、真实updated_at/version/最近结果，
Run/计划/事实/平台IO增量0；37条disabled/unscheduled配置经正式API准备完整第二页，仅测试配置。
用户在同一窗口补行序/分页/筛选/滚动确认前不标Gate2B PASS；Integration0044/HuanYu v6及旧真实run保留。
其它行业/父级全部、1d/30d、品牌和custom价格仍须逐项Query补证后交81a1，不猜测开放。
A整体PARTIAL，不合dev/main或发布；B按0044 active/0045 reserved原顺序，7d55不参与选品。

同日追加Candidate `ed6a98b95b74ca5f2dd29df0e926fdf1db577bd1`已推送交审，父8df。
ca97在旧8df对同一正式v4 run同key回读复现另一有效Team POST202→GET404，原Team/无Team均200、
Run/计划/事实/平台IO增量0。ed6仅精确GET派生资源Team，Frontend/Electron/Migration不变。
无DB method-only交错探针发现二次权限重验后未重新按最终Shop Scope查询，已退回原Owner最小返修；
原位置/视觉不受影响的证据保留，不把合成探针冒充PG或真实平台。
Owner随后交`56b9614235708faf86bb237c27dffaf8b8ae6165`、父ed6；仅在最终权威Actor下再次走
原精确Repo可见查询。ca97同一无配置/无DB方法探针确认拒绝无Shop授权的交错读取，定向边界接受；
Owner纯逻辑6/59与父版本92PG/630默认分开，56b新PG/API仍待安全核销，不把技术接受标完整Gate。
Owner额外核验异常工具输出暴露应用DB凭据。ca97仅内存审计确认同端点/Role/密码被Feature、
Integration、Main smoke三处共用，生产关系UNKNOWN；候选增量内容匹配数0，不复述凭据。
已冻结使用旧凭据的主动DB验证及发布、本机controller在加载配置/连接前拒绝；现有窗口/Profile不清理。
没有轮换Role、改共享配置或生产。须对应管理员在明确授权范围下先核对生产关联，再受保护轮换/同步；
参数12白名单本机捕获与无DB代码审核可继续，安全事项核销前不放行Gate/Green/Release。

同日22:31（Asia/Shanghai）凭据事件恢复：人类明确条件授权后，Main另有直接人类只读任务，
提供既有正式通道元数据；ca97经受信任root SSH/现有PG管理员完成生产只读比较，
实际production root配置与Backend/Signer均为`control_center_prod_app`、Role/密码不共用，
当前生产`0102dd6d051f89907bad113c35310bbab69412ec`健康且配置/进程不动。
仅轮换`control_center_dev_user`，受保护同步81a1/ca97/Main smoke、额外0106与服务器DEV配置；
三处新鲜连接通过、旧密码明确认证拒绝，Role属性/授权、业务计数及Integration单一0044保留。
Main smoke实际旧Head0034只记录，不借凭据处理迁移；0106旧目标库已不存在，不重建，密码已同步。
停止的服务器DEV容器保持停止，未来启用须正式Compose重载新配置，不直接docker start旧环境。
只回收核实归属且无活动任务的8100 Backend，5180/唯一Electron98292/Profile保留；新Backend84500
实际加载既有8df、新连接及health正常。加密恢复材料已撤除，秘密不进聊天/输出/Git。
原工具历史无受支持编辑接口，失效旧值留存如实记录，不宣称已删或全部脱敏。
凭据hold解除；Owner继续新56b必要PG，ca97随后匹配集成，A参数/原生未完成项仍PARTIAL，
不把连接恢复当成全A Gate、Green或生产发布；未受影响验收不重复。

随后Owner交测试/文档候选`183b35b4057b979f21a15e117cb2d3e8ef3b9efc`、父56b，
运行时代码/Frontend/Electron/Migration与56b相同；实际Feature PG96通过（含真实DB权限交错2项），
默认636/纯逻辑59分别记录。首轮93/1的并发领取过严FIFO断言及原因保留，按既有SKIP LOCKED/
全局一个running契约仅修测试并覆盖串行/锁首条，不修改领取算法或凭重跑撞通过。
ca97复核并匹配加载183 Backend91792，新配置与单一0044/旧计数、HuanYu valid v6保留；
5180源码仍8df但与183字节相同，唯一Electron98292/Profile未动。正式既有run同key在原Team/
无Team/另一有效Team均POST202→精确GET200，原404缺口关闭，Run/计划/事实/三类平台IO增量0。
此为定向读取尾部收口，参数及未完成原生项仍PARTIAL，不以96项或API代替完整A Gate/Green。

2026-10-13 ca97已技术认可B最小提案及独立分支安排：Owner在
`feat/product-selection-server-schedule-v1`，从精确Green3128正常no-ff merge已交A依赖
`43637bb051d2f4b3ba6c9fab608756429971edd3`，原A分支/候选完整保留。
当前仅非DDL时间规则及Run事务抽取，不新增Schema/启用自动执行，不是B闭环候选。
0044仍active、0045尚不得写/应用；A精确Green后ca97串行登记0045(down0044)，
再由Owner实施B模型/Migration。B未验代码不作为A Release目标，之后正常merge A Green。
ca97随后明确预留 `20261013_0045`（reserved，down0044），仅编号/技术审核，未激活。
仍只有A0044 active；A完整Gate及精确Green后才串行激活B，不将reserved当成写/应用许可。

2026-10-13 ca97已接回店铺登录修复，整体审查Candidate
`ce3e488bce0f8bb8f54671a792c01aa83938a92e`，匹配Renderer/Main/Preload唯一Real Electron
人工验收通过；本次原生关窗约289ms完成renderer清理，按钮恢复、无活动租约。
未变路径复用98无团队HuanYu v5→valid v6自动保存/留窗；本轮stored v6正式Accessor只读取得
正确店铺身份。首开已有人类可操作确认，历史遮罩根因仍未知，不把日志冒称修复。
正常no-ff合入`0890a5255469b47a2e593290839af549b0541d64`后54 Electron/33前端及lint/typecheck/
Real build复验通过，无Backend/Signer/经营/选品运行变化，无Migration，单一0043不变。
精确dev CI Green后交Main Release及匹配1.0.6安装交付；生产实际客户端/无团队Session可用性
未核验前不标DEPLOYED。见`docs/engineering/shop-login-close-recovery-v1-gate2-20261013.md`。

2026-10-13 当前店铺登录修复：已回读ca97人类turn `01a1313b-de4b-7eb1-ba7b-60707e70ce98`，
撤销登录Feature暂停。沿 `feat/shop-login-runtime-diagnostics-v1` 保留98d48d4并正常同步
精确Green `10938c55397442fd25854d01cf1d07628b7f027b`，禁止rebase/reset及dev代修。
仅收口超级账号无团队登录、首次页实际可操作及自然关闭后状态恢复；保留目标验证/CAS、
失败旧Session保护、成功留窗/释放锁、新店自动关闭。首次加载不把观察日志冒称根因修复。
Owner合成验证，不操作Integration/生产、不新开Electron、不写库或改0042/0043。
实际关窗49da白名单证据与无团队a61d成功证据复用，补在途检测/捕获迟到与释放定向回归。
已用deferred检测先复现98关窗后IPC未结算，再补最小终态结算/迟到保护；合成验证不替代原生Gate。
关闭恢复阶段详见 `docs/engineering/shop-login-close-recovery-v1-gate1-20261013.md`。
精确Candidate及匹配Source安装包交ca97唯一Real5180→8100→Integration验收，Green/CI后由Main发布。
已通过的选品30e8/86项/原生确认保留，不重复验收或混入本轮；后续回报明确“店铺登录修复”阶段。

2026-10-12 81a1历史授权追加（ca97人类turn `01a13030-2fd6-7990-afb9-ff7e5458c2a1`）：
沿 `feat/shop-login-runtime-diagnostics-v1` 仅FF到Green
`22403a1094b25b7569427d5383e4e28154253d79`，与已发布main db4业务树一致。
修既有店铺超级账号无团队登录：team可缺省，无团队不发x-team-id，Backend人员Session/
super/目标/lease/CAS仍权威；新店Onboarding仍要求团队，不自动选团队或增成员。
新Preload固定globalShopLoginSupported标记支持后才无团队调用，旧1.0.5明确升级提示，旧teamed兼容。
1.0.6增加本attempt的导航类别/序号、既有固定账号probe HTTP/耗时/失败布尔、脚本错误枚举及
identity/readiness布尔，首条/变化及20条脚本错误有界，结束卸载；无webRequest hook/额外平台请求。
仅观察，不猜首次遮罩根因、不自动刷新、不清Profile；两项整体PARTIAL，原生对照未完成不发布。
无Backend/Schema/Migration/Signer/选品变化，0043与专用Feature库保留，Owner不操作Integration/生产或
开Electron。精确观察Candidate、匹配Source包及Gate1交ca97；历史046/1279/全部材料保持。

2026-10-13 选品阶段历史纠偏（登录暂停现已撤销）：81a1先核验并收口已确认选品界面。
沿已保留的 `feat/product-selection-ui-restoration-closeout-v1`（原1279候选）接续，
同步ca97确认的Green `22403a1094b25b7569427d5383e4e28154253d79`，不重建或回退分支。
保留98d48d4登录候选、1178、旧选品分支、既有数据库和所有本机材料。
06bd03c为原设计对照；389030a已经恢复原策略列表/抽屉并删除ManualSelection/manualOnly，
6e6bfc6补充原生组件的弹层边界。本轮不重复重做这些已存在实现，仅处理发现的回归并补齐证据。
Real必须保留原工具栏、名称、定时草稿、状态和保存入口；未接策略保存/调度不得假成功。
保留ShopSession/Signer、有限日期回退、run、持久化、正式API及团队权限；不改Backend或0042/0043。
仅Frontend定向验证与交接，无DB写入、新Slot、平台请求、手机/SY或全局主题变更。
Owner使用4176 strictPort隔离HTTP拦截验证，不占5180/8100，不另开Electron。
普通/最大化四级类目可见、滚动、点击及父级全部尚需ca97唯一Real Electron独立证据；
完成前不将本轮选品验收标为通过、不推进该业务发布。原已发布事实不倒写或伪造。
下列登录任务授权与历史证据保留；此次仅恢复登录，不重做已收口选品。

2026-10-13 ca97已核验选品收口Candidate `30e8cc63bc3c770cee65bd02c57d56e39740e255`，
用户在对应Real Integration Electron提交普通/最大化截图并确认目前无问题；四级类目/父级全部
原生专项验收收口，既有策略结构保留。正常no-ff集成后选品86项、定向lint、typecheck、Real build通过。
本轮只追加测试与登记，Frontend运行源码/Backend/Electron/Migration相对Green无差异，单一0043不变。
精确dev CI后交Main Release；未宣称生产DEPLOYED，不混入98登录关闭挂起返修。
详见 `docs/engineering/product-selection-ui-restoration-closeout-v1-gate2-20261013.md`。

2026-10-12 登录任务：按ca97已核验的人类原始授权
`01a12c59-4ac4-70f0-894d-5aed7cd7731c`，从精确Green
`1718abe117c90842c8d39859a074fa988360f070` 建立
`feat/shop-login-runtime-diagnostics-v1`。仅补店铺登录一次点击的白名单阶段诊断、
打开中/请求去重/有界超时与失败恢复反馈；列表和详情仍共用既有登录流程。
已打开捕获窗允许再次点击，经当前权限复核只置前，不重复租约/open/save；
旧1.0.4不附加新参数，仅新Preload固定能力标记允许correlationId。
正式1.0.5仍禁DevTools，不改变Origin/主Frame/sandbox、Session/Profile或Signer边界。
固定userData诊断文件只含随机关联ID、枚举/布尔值/状态/耗时，不含身份、凭据、URL或原始异常。
无DB/Schema/Migration/平台请求；旧选品1279候选和旧分支/本机材料保留，0042/0043不改。
Owner完成Gate 1和匹配Source安装包交ca97；唯一生产故障窗口不动，实际点击、根因与
原生登录复验由ca97协调，CI/发布由ca97/Main按Gate执行。没有点击证据不能称根因已修复。
选品界面恢复另行交接，原生普通/最大化尺寸仍待复验；不将本诊断候选混作选品验收。

2026-10-12 ca97已审查诊断Candidate `046fd03e7124a829cb2659ba75b6c12fe0a8681d`，
正常no-ff合入 `ddd523d08ae7896498f2950123c5bdf044568a50` 并复验；唯一Real Integration
实际HuanYu登录完整走通，Session v3→valid v4、租约释放且浏览窗保留，无新增经营任务。
原生截图/点击工具受限由用户代点，未把工具故障当业务根因。旧生产无反应仍UNKNOWN、未DEPLOYED；
精确dev CI、Main Release及匹配1.0.5生产实际点击分别收口，详见
`docs/engineering/shop-login-runtime-diagnostics-v1-gate2-20261012.md`。

2026-10-11 当前81a1任务：从精确Green
`06992f4f3ee03e2ad689b25e7a4cb5837ce0d359` 接续
`feat/shop-login-session-sync-v1`。仅完成店铺列表/详情共用登录入口、目标店铺身份核验、
候选Session权威验证后原子保存、成功后结束捕获但保留浏览窗口，以及显式单项每日Session失败恢复。
支持平台和管理权限沿用既有规则；valid亦可登录。首次新店Onboarding仍成功保存后自动关闭。
失败候选不覆盖原Session；不将网络、签名或未确定平台错误标为认证失效。
Integrator已分配专用空库 `control_center_feat_shop_login_session_sync`，Owner
`control_center_dev_user`，仅本地受保护凭据经35433访问，Feature端口8101/4176 strictPort。
只升级既有迁移至单一 `20261010_0043`；无新Schema/Migration、Slot FREE，不使用旧选品库。
恢复复用既有retry API/队列/锁和Job唯一键，只覆盖原DAILY的明确Session准备失败，
新鲜VALID版本通过权限/启用/去重检查后至多一次；保留原失败和累计次数，普通重试上限不变。
Owner只完成Gate 1与匹配Source SHA的正式桌面包交ca97；真实登录/生产恢复由ca97/Main协调。
禁止Owner写Integration/生产、合dev/main或发布。旧选品界面恢复已完成，不再重复审核或改设计。
Gate 2候选 `9fc6409c015bec767a5d4a72304a5bb0c0d9e855` 已整体审查ACCEPT并正常no-ff合入
`62cc491cb023a2e1b5827d03a7923f370e6711a4`。同一Real Integration Electron已实际验证HuanYu
正常登录自动保存v2、留窗、重复点击不另存、关闭重开v3且租约释放；无新增经营Job/Item。
候选Backend604、Frontend614及合并后PG37/Session15/Electron27与Real build通过；负向/首次添加
合成覆盖和真实操作分开记录。精确dev CI成功后交Main Release；匹配1.0.4实际安装及生产两店
2026-10-10受控恢复仍待正式发布核验，未DEPLOYED。详见
`docs/engineering/shop-login-session-sync-v1-gate2-20261011.md`，不复制集成Session到生产。

2026-10-11 新一轮选品体验收口：81a1 从精确 Green
`a9931a8f8b329bb5e5e79f9e44fd42294ca5d633` 创建
`feat/product-selection-experience-fixes-v1`，保留原策略列表/抽屉和手动接入。
仅收口本次主动获取的消失消息、视频区间格式、差评率百分比、24小时店铺类目缓存与弹层边界。
复用 retained `control_center_feat_product_selection`（单一0043）、Feature 8101/4176；无新Schema或Migration。
0042/0043、Session/Signer、日期规则、事实与权限不改；不新增策略保存、调度、百应或手机能力。
Gate 1候选 `6e6bfc63f8ee5f3155c134fcb527f44eb9bf4508` 已经ca97整体审查并no-ff合入
`5eababba8b0c466f65ad0ec437a1b66e39d96b90`，同一Integration的5180/8100实际加载该候选。
技术与真实读取验证通过，按用户本轮指定继续dev精确CI及Main交接；旧41e预览不作为本轮证据。
原生普通/最大化菜单尺寸人工确认未单独取得，明确交Release Gate核对，不以浏览器拦截替代。
开发会话不合并dev/main、不发布；详细范围和证据见
`docs/engineering/product-selection-experience-fixes-v1-gate2-20261011.md`。

当前状态（2026-10-11）：选品手动Candidate `41e3116e0e176761f3a3fbb29e199283ce61c95c`
通过Gate2，no-ff Merge `3448b7d74651bcaab3f39dbeff97aee9a5fcea83`；Integration单一0043。
HuanYu正式run `72f42fff-1996-4d59-9c30-30104f373e63` 真实10条入库及10条basic_info成功，
用户确认Real列表/详情/刷新。此run首选10-04～10-10成功、未触发备用；窄621000704第一页补查有PG覆盖，
不把该业务码普遍解释为日期未就绪。0042/0043 Slot统一released，Feature库retained，失败历史保留。
下列旧UI_ONLY/PARTIAL为阶段记录；当前手动闭环与CI/Release边界见
`docs/engineering/product-selection-manual-v1-gate2-20261011.md`。未生产核验前不标记DEPLOYED。
达人登录、策略保存、定时、手机及百应仍未接入，不能假成功。

本期 Feature 登记（2026-10-08）：81a1 `feat/product-selection-frontend-v1` 从 ca97 确认的 Green
`b34e43cb90356e03d2f793c4146c6775a11f5ab3` 开发选品库前端与 Mock 交互，状态 `UI_ONLY`。
复用 framed 导航、既有列表/分页/Drawer/表单/ShopSelector/主题；采集任务与商品库仍占位。
typed service 为前端草案，Real 不请求猜测接口、不回退 Mock。无 Backend、Schema、Migration、Worker、
真实平台、真实调度或达人登录/Session 保存。Gate 1 后交“集成ca97”唯一 Integration Electron 验证 Mock
与 Real 边界；Green 后交原发布会话，开发会话不发布。旧分支、提交与本机忽略材料保留。

2026-10-09 用户授权按两个阶段接续本 Feature：先完成紧凑候选列表、详情首屏和说明精简的前端返修，
仍为 UI_ONLY，无新增业务数据库/Migration；由 ca97 加载精确新候选进行集中页面复验。
前端确认后才实施罗盘手动选品最小闭环（条件→榜单请求→候选持久化→basic_info补充→正式查询）。
该阶段复用ShopSession/HTTP/Signer/商品模块授权与团队隔离；必要Feature DB与Migration Slot由ca97分配。
不扩展百应、达人登录、每小时监控、手机任务或自动上架；开发会话不操作main/生产，Mock不能替代真实闭环证据。

选品接入资源登记（2026-10-10）：81a1 沿用 `feat/product-selection-frontend-v1`，基线
`b34e43cb90356e03d2f793c4146c6775a11f5ab3`。前端候选 `06bd03c0fa61b00251063e21350cd0cc5445afe5`
及诊断补丁 `819ca33ba6548030e418320c6bb80ba046beb842` 尚未合入 dev；Frontend/Electron 树相同，
Mock 验证不代表真实入库。两表、业务专用 `product_selection_runs`、观察的可空 `last_run_id`
及 Real 查询已在阶段候选实现；技术复核通过但仍为 PARTIAL，空榜单、失败和中断有独立记录，
不增加通用队列、Worker、策略调度或自动平台重试。具体事务/幂等约束见选品资源登记文档。
0041 已在 Integration/生产应用，旧 Slot released；本 Feature 保持唯一 active Slot，串行链为
`20260924_0041 → 20261010_0042 → 20261010_0043`。0042 已在 Feature 库应用，不改写、不释放；
追加 `20261010_0043_product_selection_runs_v1`，revision `20261010_0043`，down `20261010_0042`，
由 81a1 编写且已在 Feature 库应用；两项随同一完整候选验收后一起释放，不另开第二个活跃 Slot。
独立库 `control_center_feat_product_selection` 现为单一 `20261010_0043`，ShopSession=0，Owner `control_center_dev_user`，
受信任 `35433` 隧道及 SCRAM 连接/回滚 DDL 探针通过；应用角色无 CREATEDB/CREATEROLE/SUPERUSER。
81a1 本地忽略连接及实际库名已核验；保持现有库和0042事实，未知渠道/日期/类目转换不猜测实现。
Feature Backend `8101`、Frontend `4176 --strictPort`，仅 Feature Owner 运行；Integration 仍为
`8100/5180 --strictPort` 与唯一 Electron。仅登记/评审，不代 Feature 写 Migration，不发布生产。

- Gate 1 由 Feature Owner 完成：自检、测试、文档/契约同步、提交，并以正式 Handoff 交给 Integrator。
- Gate 2 只在 Integration Worktree 执行：读取候选提交、做集成验证、解决真实冲突并决定接受或拒绝。候选本身的业务 Bug、缺测试或契约缺口必须退回原 Feature Owner；Integrator 不代为开发业务修复。
- Gate 2 通过后只允许 `git merge --no-ff feat/*` 合入 `dev`。集成后 `dev` 失败时，应拒绝候选或在共享历史上 `git revert`，禁止 `reset`、改写历史、未审查的 rebase/cherry-pick。
- Release Gate 要求 Green `dev`、验证证据和发布说明完整；未经该 Gate 不得合入 `main`。

### 数据库、运行环境与本地材料

- Schema 变化由 Feature Owner 编写 Alembic Migration；同一时刻只能有一个登记的 Migration Slot。Integrator 负责分配 Slot、验证候选，不替代 Feature 编写新 Migration。
- Feature 使用自己的可重建临时/Feature 数据库；Integration 只写 `control_center_integration`；Main smoke 只写 `control_center_dev`；未来生产环境必须独立。不得混用或把凭据写入 Git。
- 固定运行隔离：Main `8000/5173`、Integration `8100/5180`、AI 前端 `5174`、SSH Tunnel `35433`。Vite 必须显式端口并启用 `--strictPort`。Mobile 端口以当前 `mobile` 配置为准，不能因历史记录把 `5175` 视为永久保留端口。Integration Electron 如需联调只指向 `5180`，且不启动第二个 Electron。
- `.dev-runtime/` 是 Main 偏置运行管理器，记录的 PID 必须结合真实进程校验，过期记录不是唯一事实。临时脚本、日志、截图、build/test artifact、PID 与本机密钥必须清理或被 Git 忽略，并在 Gate 1、Gate 2 检查。
- `AGENTS.override.md` 仅可作为 Worktree 本地覆盖文件，必须通过该 Worktree 的 `.codex/git-exclude` 忽略，禁止提交。版本化临时文档目录规则由 `.gitignore` 统一定义。

## 1. 项目定位

本项目是“电商 AI 中控台 / 电商自动化控制平台”。

核心能力：
- 多平台、多店铺、多员工、多设备管理。
- 中控台触发 RPA、Python、Node、Browser、EXE 等执行能力。
- Worker 负责设备注册、心跳、任务领取、执行和结果回传。
- Backend 负责业务数据、权限、任务、Session、API、审计。
- Electron 负责桌面壳、本地系统能力和 Worker 进程管理。
- Frontend 负责 UI、交互、状态展示。
- AI 仅用于明确需要的结构化数据分析，不作为基础执行链路的默认依赖。

项目采用：**模块化单体 + 分层文档 + 渐进式演进**。

不要求第一阶段设计所有未来业务，但新增功能必须遵守既定模块边界、契约、抽象与复用规范。

---

## 2. 固定技术栈

除非项目负责人明确要求，否则不得随意替换。

### Frontend
- Vue 3
- TypeScript
- Vite
- Vue Router
- Pinia
- Naive UI
- Axios
- TanStack Vue Query
- vee-validate
- Zod
- Apache ECharts
- dayjs
- VueUse
- Vitest
- Playwright
- ESLint
- Prettier
- pnpm

### Electron
- Electron
- TypeScript
- `contextIsolation = true`
- `nodeIntegration = false`

### Backend
- Python
- FastAPI
- Pydantic
- SQLAlchemy 2
- Alembic
- PostgreSQL
- HTTPX
- pytest
- Redis：按阶段引入
- MinIO/S3：文件存储需要时引入

### Worker
- Python
- 独立于 Electron Renderer 的长期运行进程
- 通过服务器接口注册、心跳、领取任务、回传状态
- RPA / Python / Node / Browser / EXE 作为 Worker 下属执行能力

### 特殊 JS Runtime
- Node.js 仅用于 Electron 或确实需要 JavaScript Runtime 的平台能力
- 禁止无必要地建立第二套 Node.js 业务后端

---

## 3. 系统边界

```text
Frontend
    ↓
Electron Preload / HTTP API
    ↓
Electron Main          Backend API
    ↓                       ↓
本地系统能力             PostgreSQL
    ↓                       ↓
Worker ←────────────── Task / Session / Config
    ↓
RPA / Python / Node / Browser / EXE
```

职责：
- Frontend：界面、交互、路由、前端状态、服务端数据展示。
- Electron：桌面窗口、Preload、IPC、本地文件、进程管理。
- Backend：业务数据、权限、API、任务、Session、Credential、审计。
- Worker：设备常驻、心跳、Task Claim、Lease、执行与结果回传。
- Skill/RPA：完成具体业务能力，不承担中控台业务编排。

禁止跨层偷渡职责。

---

## 4. 分层阅读规则

处理任务前必须先判断修改范围。

阅读顺序固定：

```text
根 AGENTS.md
↓
对应子系统 AGENTS.md
↓
子系统 docs/00-文档索引.md
↓
只读取当前任务需要的专项文档
↓
检查现有代码/组件/契约
↓
再实施
```

### Frontend
涉及 Vue、页面、组件、Router、Store、样式、Design Token、前端 API：
- 先读 `frontend/AGENTS.md`

### Electron
涉及 Main、Preload、IPC、Window、本地文件、进程、打包：
- 先读 `electron/AGENTS.md`

### Backend
涉及 FastAPI、PostgreSQL、Migration、API、权限、Session、Task：
- 先读 `backend/AGENTS.md`

### Worker
涉及 Worker、Heartbeat、Claim、Lease、Skill、RPA、执行日志：
- 先读 `worker/AGENTS.md`

跨系统任务必须分别读取涉及子系统的 AGENTS 和专项 DOCS。

禁止为了“保险”无差别读取所有文档。

---

## 5. 最高优先级实施约束

### 5.1 禁止猜想和自编契约

任何代码修改前必须优先查找：
1. 现有代码。
2. 现有类型。
3. 现有 API Contract。
4. 现有数据库模型。
5. 现有组件。
6. 现有 IPC Contract。
7. 现有 Skill Contract。
8. 对应 DOCS。

禁止自行猜测或创造：
- API URL
- 请求字段
- 返回字段
- 数据库列
- 状态枚举
- IPC Channel
- Event 名称
- Skill ID
- 错误码
- 权限码
- 第三方平台字段
- 配置键
- 文件路径协议

如果权威契约不存在：
- 先确认是否应新增正式契约。
- 新增契约必须落入对应 DOCS / schema / type。
- 仍无法确认的外部事实不得伪造实现，应明确标记阻塞点。

禁止“先随便写一个能跑的，后面再说”。

### 5.2 可以抽象的必须优先抽象

满足任一条件时，必须优先建立抽象层或复用现有抽象：
- 同类逻辑已经出现 2 次或预计会跨页面/跨模块复用。
- 同一业务实体会被多个页面使用。
- 同一种 API 调用模式会重复出现。
- 同一种 RPA / Skill 输入输出遵循统一协议。
- 同一种平台接入存在不同实现。
- 同一种 UI 结构在多个页面出现。
- 同一种 Electron IPC 能力可能被多个页面调用。
- 同一种错误、状态、权限、日志模型会跨模块使用。

常见抽象：
```text
UI → shared/components
领域实体 → entities
业务动作 → features
HTTP → shared/api
后端平台请求 → connector / adapter
外部依赖 → adapter
Worker 执行器 → executor
Skill → standard contract
IPC → typed bridge
```

禁止复制粘贴已有实现形成第二套近似逻辑。
同时禁止无业务依据的“万能抽象”，抽象必须有明确语义边界。

### 5.3 有组件必须优先用组件

实现 UI 前必须先检查：
1. Naive UI 是否已有组件。
2. `shared/components` 是否已有公共组件。
3. 当前领域是否已有可复用组件。
4. 当前页面是否已有一致模式。

存在可满足需求的组件时禁止手写替代。

已有 PageHeader、PageSection、DataTable、StatusTag、EmptyState、ErrorState、LoadingState、ConfirmDialog、ShopSelector、DeviceSelector 等公共能力时，不得创建第二套近似版本。

### 5.4 优先使用成熟第三方库，禁止重复造轮子

已有依赖可稳定解决的问题，优先使用既定第三方库。

典型：
- Router → Vue Router
- Client state → Pinia
- Server state → TanStack Vue Query
- HTTP → Axios / HTTPX
- Form → vee-validate
- Schema → Zod / Pydantic
- Chart → ECharts
- Date → dayjs
- ORM → SQLAlchemy
- Migration → Alembic

禁止手写自制 Router、请求缓存、表单框架、日期工具集、ORM、Migration 等重复基础设施。

新增第三方库前必须先确认现有依赖不能合理解决，避免重复引入同类库。

---

## 6. 复用与依赖方向

优先级：

```text
现有能力
↓
现有公共抽象
↓
现有第三方库
↓
新增领域抽象
↓
最后才是新增一次性实现
```

禁止依赖方向错误：
- shared 不依赖 pages/features。
- entity 不依赖 page。
- Backend shared 不依赖具体业务模块。
- Worker core 不依赖具体某个平台 Skill。
- Electron Main 不依赖 Vue 页面实现。

---

## 7. 核心稳定 ID

长期稳定：
- `user_id`
- `shop_id`
- `device_id`
- `task_id`
- `skill_id`

后续可新增：
- `credential_id`
- `session_id`
- `workflow_id`
- `workflow_run_id`
- `order_id`
- `product_id`

禁止使用店铺名称、电脑名称、员工姓名建立长期关系。

---

## 8. 数据库演进

允许渐进式新增：
- 表
- 字段
- 索引
- 关系
- Migration

修改数据库必须：
1. 先判断是属性、实体还是关系。
2. 通过 SQLAlchemy Model + Alembic Migration 演进。
3. 保持稳定 ID。
4. 不直接手改正式数据库结构。
5. 不让 RPA 直接连接 PostgreSQL。

---

## 9. API / IPC / Skill 契约

所有跨边界通信必须有明确契约：
- Frontend ↔ Backend：API Contract
- Frontend ↔ Electron：IPC Contract
- Backend ↔ Worker：Task/Device Contract
- Worker ↔ Skill/RPA：Skill Contract

契约至少定义：
- 输入
- 输出
- 状态
- 错误
- 版本（需要时）
- 必填/可选字段

禁止调用方自行猜测被调用方行为。

---

## 10. 修改范围

每次任务：
- 只修改当前任务必须文件。
- 不做无关重构。
- 不顺手更换技术栈。
- 不删除架构预留能力。
- 不为单页需求污染全局。
- 不把临时业务塞进 shared。
- 不复制公共组件。
- 不直接跨层调用。

必须跨模块修改时，要说明原因和影响面。

---

## 11. 文档同步

以下变化必须同步 DOCS：
- 目录结构
- 模块边界
- API Contract
- IPC Contract
- Skill Contract
- 数据库核心关系
- Design Token
- 通用组件规则
- 通用状态/错误码/权限码

普通内部实现调整不需要修改全部文档。

---

## 12. 开发前检查清单

- [ ] 已读取根 AGENTS。
- [ ] 已读取目标子系统 AGENTS。
- [ ] 已读取任务对应 DOCS。
- [ ] 已搜索现有组件/方法/类型/接口。
- [ ] 已确认没有重复实现。
- [ ] 已确认字段、URL、状态、权限等不是猜测。
- [ ] 已确认能复用的抽象已复用。
- [ ] 已确认第三方库已有能力优先使用。
- [ ] 已明确本次修改范围。

---

## 13. 完成标准

任务完成不等于“页面能显示”或“代码能运行”。

还必须：
- 边界正确。
- 无重复抽象。
- 无随意硬编码。
- 类型明确。
- 契约一致。
- 错误有处理。
- 验证通过。
- 没有无关改动。

---

## 14. 后端业务层级与身份边界（硬规则）

新的管理端业务能力必须遵守：

```text
API → Service → Repository → Database
```

- API 只负责 HTTP、DTO、参数解析，以及未来 Authentication / Permission Guard 的插槽；禁止承载核心业务流程、直接完成业务写入或跨 Repository 编排事务。
- Service 负责业务规则、状态校验、跨 Repository / Domain Service 编排和事务边界。
- Repository 只负责 Query、Persistence、Lock 与 Pagination；禁止承载权限、UI 语义或跨领域流程。
- Backend 内部的 Scheduler、Maintenance 和未来 Server Job 也必须调用正式 Service；禁止绕过 Service 直接写业务 Repository 或业务表。
- Authorization（例如未来 `schedule.manage`）与业务合法性（例如 Device 已停用）必须分离。权限不得进入 Repository，业务合法性不得交给 Frontend 判断。
- 未来 Data Scope 必须在 API / Query 边界实施；禁止 Backend 返回全量数据后由 Frontend 本地过滤实现数据权限。
- 员工 User Authentication 与 Worker Device Token 是两套独立 Identity；Worker 不使用员工 JWT，员工管理 API 不使用 Device Token。
