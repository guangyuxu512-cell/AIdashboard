# 选品前端验收状态与真实接入资源

2026-10-10，Integrator ca97，Feature Owner 81a1。独立数据库和新 Migration Slot 已分配；Owner已完成固定解析、两表及数据库查询API，真实执行闭环仍为PARTIAL。请求链路成功证据可复用，本轮不发布生产。

## 提交与前端验收

| 项目 | 精确状态 |
| --- | --- |
| Green 基线 | `b34e43cb90356e03d2f793c4146c6775a11f5ab3`；资源登记前 ca97 dev/origin/dev 一致且 clean |
| 初次核对 Owner | `C:\Users\Administrator\.codex\worktrees\81a1\中控台`，`feat/product-selection-frontend-v1`，HEAD/origin 为 `819ca33ba6548030e418320c6bb80ba046beb842`，clean；此后 Owner 的接入准备修改继续保留 |
| 资源同步 | ca97 登记提交 `675016769ba0b55f8ed42c15e7500b0c6291f968` 已推送 dev；Owner正常merge后为 `0c75ef05e36e6c7f5ce8137a6bd81e4102f7e515`，再merge工程Green `b746ab1397f4637a5b7beb4face5c197cfdeeac7` 后为 `ebae1ba6536c37e40d383d2214aaab612ad8d836`。819ca33与最终前端树保留，不将资源merge当作业务Gate通过 |
| 前端最终候选 | `06bd03c0fa61b00251063e21350cd0cc5445afe5`；Gate 1 有完整 Handoff，含 lint/typecheck、41 定向单测、13 Mock E2E、Real build |
| Integration 返修复核 | 06bd03c 独立 lint/typecheck/Real build、41 单测、3 定向 Mock E2E、diff check PASS；前一 91461d4 Review2 返修及 Real 无回退证据保留 |
| Electron | 唯一既有开发窗口已从最小化恢复；原生可访问性核对5180选品库、候选池/采集任务/策略入口、32条演示候选。运行仍为06bd03c Mock快照。原生截图重新绑定后仍超时；已有交互/主题确认保留，尺寸收尾等待最终人工确认，不用浏览器截图补写Electron PASS |
| dev 合并 | 06bd03c 与 819ca33 均不在基线 dev，未合并，无 Merge Commit；资源登记不代表业务合并或 Green 新功能 |
| 诊断补丁 | 819ca33 是 06bd03c 的直接后续，仅请求层、9 项定向测试及 Backend 说明；两提交 Frontend tree 均为 `0cfd65b3eb7573a2ba5be6b9a7cef08977f85e84`，Electron 树亦相同。定向审查 PASS，不等于完整 Gate 2 |

前端仅确认界面及 Mock 交互，不证明真实采集、持久化、策略保存或调度完成。恢复 Real 后必须没有 Mock 残留/回退，未接入部分如实不可用。

## 已确认取数事实及未知边界

正式认证来自 HuanYu 数据库 ShopSession v1，平台 shop_id `243321624`；链路为 Accessor → 819ca33 DouyinApiClient → 既有 Signer。两次榜单均 HTTP 200、整数 st=0、10 条，basic_info 成功且商品身份匹配。签名 Cookie 与实际 HTTP Cookie 一致，签名后复用同一请求并保持业务 Query 编码。本轮不重播这些Backend诊断或追加认证探针；仅正常页面取证，不把页面自动请求说成新的入库闭环。

- 榜单固定路径 `product_rank/video_bring_good`；响应 `data.data_result`、`data.page_result`，商品 ID 为字符串。
- 成功样本为 2026-10-02～10-08、date_type=21、rank_data_type=1、第2页/10条，以及已记录的12个业务字符串参数；这是一次具体条件，不是生产默认、所有渠道/周期的映射依据。
- cate_list 节点 cate_id/cate_name/children、样本行业/类目层级及 basic_info 的 cid_info、first_on_shelf_time 已取得；请求店铺与返回商品商家分离。
- 视频四项 value_range 保留端点、原始 unit 和类型；price 尺度、成交单/件含义未确认。差评率原值 `0.00205018686599039`、unit=4，不换算百分比或用于筛选。
- 商品卡/短视频区分、相对日期与枚举通用含义、类目选择的通用转换、未实测条件仍未知。Real 未确认选项不能静默映射或使用 Mock 补齐。
- 旧 621000704 唯一根因未确定，不阻塞已确认字段和资源准备。

## 两表审查与执行状态缺口

候选身份使用 `(team_id, platform, platform_product_id)` 唯一键；来源观察使用 `(candidate_id, request_shop_id, source_scope_hash)`，不同店铺/期间/条件不互相覆盖。source_context 仅白名单业务参数，来源 hash 版本化且不含页码、认证或追踪值。Team/创建人来自 ActorContext，请求 Shop 指现有授权 Shop，不是商品商家 ID。

平台 I/O 在短事务外；落库前复核权限及停用/移除状态。PostgreSQL upsert/条件回写防重复与迟到旧响应，双 Session 实测是 Gate 1 前置。basic_info 失败保留候选及此前有效值，真实0与缺失分开；列表/详情先做 Team+当前 Shop 授权及来源选择，再排序分页。

两表已保存候选与成功来源事实，但不能表达无候选的成功空榜单或请求失败。依据用户后续授权及80ed841审核稿，技术审核允许新增一张业务专用 `product_selection_runs` 和观察的可空 `last_run_id`；实现条件见下节。现有 Task、经营采集和 AI Job 各有领域约束，不得挪用。不增加通用队列、Worker或策略调度；方案获准不代表实现或完整Gate通过。

降级按来源表→候选表，仅允许在可重建 Feature 库测试，明确删除新选品数据；已有正式数据时应用回退保留 Schema/事实，数据处置另走 Release Gate。无已批准保留期，不增加自动删除。

## 实际资源与初始化交接

| 资源 | 分配结果 |
| --- | --- |
| DB | `control_center_feat_product_selection`，管理员创建独立空库后，由 Owner 通过既有 Migration 初始化；Owner `control_center_dev_user`；不复用 Availability/Integration/生产 |
| 应用连接 | 既有 `127.0.0.1:35433` 受信任 SSH 隧道已恢复；StrictHostKeyChecking=yes；实际 SCRAM 连接成功，当前 DB/角色匹配 |
| 最小权限 | CREATEDB=false、CREATEROLE=false、SUPERUSER=false；Feature 库建表/改列/索引权限探针 PASS，事务已回滚，前后 public 表数均0 |
| 初始化及现状 | 初始0041/44表、0042/46表及两表模型差异0已核验；Owner现已执行0043，Integrator最新只读核对DB和Owner工作树代码单一 `20261010_0043`，1候选/1观察为0042回滚保留测试事实，run=0、ShopSession=0、角色仍最小。未执行共享环境迁移或平台任务；Owner `.env` Git Ignore PASS |
| HBA | 仅新增本 Feature DB + 应用角色 + `172.17.0.1/32` SCRAM 规则，位于 reject 前；解析错误0，reload，无服务重启；其他规则不变 |
| HBA 备份 | 持久化数据卷中的 `pg_hba.conf.before-product-selection-20261010T112247Z`；SHA-256 `4d6671e093bc9fcb1665d207a08ade58806c4a19e7d34b200ea686080ca1eb7a` |
| Head 与 Slot | Integration/生产已核验单一 `20260924_0041`，旧0041 Slot released；本 Feature 唯一 active Slot 覆盖已应用Feature库的0042/0043（0043 revision `20261010_0043`，down `20261010_0042`）。不改写0042、不另开活跃Slot；两文件由Owner编写，完整候选一起验收 |
| 端口 | Owner Backend 8101，Frontend 4176 strictPort；只登记未启动。Integration 保持8100/5180及唯一 Electron，真实平台由 ca97 协调 |
| 凭据 | 复用 Owner 本地忽略配置中的既有应用角色凭据，仅更改目标数据库；不得回传完整连接串，不能继续使用旧 Availability 库 |

81a1已完成两表、事实服务和只读API，不重复安排开发。部分候选80ed841对团队引用保护的返修复核PASS：Integrator独立65项定向测试通过，纯内存探针确认引用检查包含候选；Owner的21项PG及409/204用例已审阅，未宣称Integrator独立重跑。整体仍PARTIAL，未合入dev、未释放Slot。

Owner已正常merge资源登记到 `7060899e7284527bdde25a06335d4aec15eab297`，当前未提交的run/Real读取适配成果保留。Owner报告38项真实PG/正式API合成平台测试、41项前端定向测试和1项Real失败/空态E2E通过；0043降级保留0042事实、非空run拒绝降级通过。上述是实施中证据，不是最终Candidate、完整Gate1、真实平台请求或Electron验收。

## 手动运行技术决策

业务专用run方案允许实施，由81a1将正式DTO、Model、Service/API和本节约束同步到Backend契约。run保存Team/发起User/请求Shop（RESTRICT）、submission_key、版本化白名单条件及明确日期、状态/阶段、实际结果计数、安全错误和租约。只增加本业务必要结构，不重做两张事实表。

- `(team_id, created_by_user_id, submission_key)`保证回执幂等；相同原始用户条件必须返回原run和已冻结日期，不能因跨日重新计算相对日期而误判409或再次请求。相同key不同用户条件409。活动同Team/Shop/规范条件由PostgreSQL部分唯一约束去重，处理特定唯一冲突返回同一run，不把刷新当提交。
- 同一run表以可空自引用`reused_run_id`保存重复提交回执；每个接受的用户/key均先持久化独立映射，再返回202。回执行不领取、不计作执行、不复制执行计数或租约；只能指向同Team/Shop/条件的根执行。公开回执为`receipt_id/submission_key/execution_run_id/reused/execution`；执行DTO不返回其他提交人的key。key和原始条件校验在相对日期重算前完成；不用JSON别名关系、GIN索引或advisory-lock框架。
- pending只来源于明确手动提交。复用Backend现有lifespan和有限 `to_thread` 执行模式，短事务领取、平台I/O在事务外；模块执行开关默认关闭，复用现有配置体系，不复用经营/AI队列，不增加定时或自动平台重试。
- lease_id/有效期须通过数据库条件更新或行锁，与本次事实写入、计数及last_run_id关联处于同一短事务。不能只在Python中检查租约后由现有FactService独立commit，留下检查/写入竞态；复用现有服务/Repository，不另造事实写入实现。每次HTTP前和事实写入前复核当前User/Team/模块/Shop授权及启用状态。
- 无候选的合法成功空列表记录succeeded及真实0计数；取得榜单前失败记录failed/安全阶段，未知计数为null；候选保存后补充缺失或失败为partial，旧有效事实保留。计数明确指取得、有效写入（包括幂等更新）及补充结果，不把未取得值填0，不将去重更新数冒充新增候选数。
- running租约到期记录interrupted且保留事实，不自动重发结果未知的请求；旧执行者不得续旧租约或写回。权限撤销/停用后停止后续HTTP及事实写入，仍由有效执行租约安全结束run并记录固定安全原因，不能永远留running。关闭时不得把取消协程当作已停止线程/HTTP；依靠有限超时及租约屏障挡住迟到写回。
- Observation.last_run_id只表示当前有效事实的来源，写入前校验run的Team/Shop一致且满足既有新旧执行排序。历史run保留条件、状态及计数，不承诺不可变商品/逐项失败快照；旧run关联被新事实替换后，UI不得把空关联列表说成当时没有候选。不为此增加第四张Item表。
- 继续既有Actor/Module/Shop Scope，普通读取当前Team/授权Shop，超级账号创建需明确Team。Team引用检查纳入run，覆盖只有空榜单/失败run时的409。平台业务码保留安全int/string原类型；无Cookie、Token、签名、完整URL、原始响应或任意异常消息进入run、日志和错误详情。
- 0043只增加run及必要关联/约束；0042文件保持字节和逻辑不变。0043降级仅允许可重建Feature库、run为空，保留全部0042事实；有run则先拒绝，不执行破坏性DDL。正式数据存在时应用回退保留Schema，不自动降级或清库。

Gate 1须覆盖跨Session提交/领取、回执丢失及跨日幂等、成功空结果、失败前无候选、basic_info部分失败、执行中撤权/停用、租约过期及迟到写回、刷新零平台请求、只有run的Team引用、0042事实保留与0043降级拒绝。

## 最小请求映射与会话边界

补充技术审核：0043同表保存独立回执，列`reused_run_id`自外键RESTRICT。canonical为NULL，回执行status=reused且无计数/错误/lease/执行起止，不领取或列入latest。不同提交key和不同用户各保留自己回执，活动复用关系与接受回执同事务提交；不增加JSON别名/advisory锁。公开POST明确receipt_id、调用者submission_key、execution_run_id、reused及execution；执行DTO不含其他人的key。回执ID读取先复核两侧同Team/Shop/canonical关系与当前授权。0043尚未进入共享环境，技术审查不等于完整Gate。

现有成功请求只证明该组实际字符串参数。此次已有HuanYu正常罗盘页面可见短视频榜、近7天及明确日期2026/10/03～10/09，当前类目为“智能家居 / 餐饮厨具 / 厨房小工具”，正常显示10项。浏览器支持的只读页面/控制台没有取得该次Network业务Query；因此页面标签与实际`date_type`、日期边界、industry/category ID的对应关系仍未冻结。不由接口路径或Referer推断映射，也不从旧10-02～10-08推导通用规则。可继续DTO/状态/数据库与Real读取适配；未冻结条件的执行选择需明确不可用。

最少补证据为既有合法罗盘页面的同一次“短视频＋近7天＋当前类目”正常操作：仅登记所选模式、页面明确日期、12个白名单业务参数及分页。若父级“全部”仍不明确，再做一次单因素类目操作；不覆盖所有周期/品牌/价格、不再做认证成功测试。优先复用已保存页面证据，无Cookie/cURL交接。自定义价格、其它周期、首次上榜及未确认单位继续不支持。

Feature库ShopSession=0，不复制生产Cookie，也不增加跨库认证桥或身份模块。Feature网络测试需本环境正常授权的Session；最终候选Integration真实闭环由ca97使用Integration正常登录会话、隔离Signer及8100/5180验证，Owner不得切库写Integration。若已有Integration Session不可用，只请求一次正式店铺登录；生产只读旧证据不冒充新候选入库闭环。

## Owner两表阶段验证

Owner在独立Feature库完成0041→0042→0041→0042，模型与Migration差异0，旧域表记录保留；当前单一0042、46表、新事实表无测试残留、ShopSession=0。生产/Integration未迁移，没有复制凭据或启动平台循环。此前一次元数据检查因验证器未加载引用表而报错，修正验证器加载users/teams/shops后通过，不是Migration回写失败。

实际Backend命令及结果：

- `python -m pytest -o addopts= tests/test_product_selection_api.py tests/test_douyin_product_selection.py tests/test_douyin_api_client.py tests/test_product_selection_source.py -q`：56 passed。
- `python -m pytest -o addopts= -m integration tests/integration/test_postgresql_product_selection.py tests/integration/test_postgresql_product_selection_migration.py -q`：19 passed。
- `python -m pytest -o "addopts=-m 'not integration'" -q`：557 passed、95 deselected；95项不表示整套PG已验证，只对本轮上述19项显式执行。

API验证注入人员Principal和Feature连接，实际Actor/Team/模块/店铺授权链保持；未启动应用lifespan。夹具为合成商品，不能替代本候选真实请求、入库和Real展示。公共TestClient产生一项现有Starlette/httpx弃用警告，未为此改依赖。

Frontend/Electron树与819ca33相同，本阶段没有重跑UI/桌面测试或新增窗口。保存策略、手动执行和类目API未接通；两张事实表不能保存无候选的空成功/失败运行，相对周期/渠道转换也未冻结。完整Gate1继续BLOCKED，只交阶段候选供审查，不进入业务dev合并或发布。

## Owner运行记录与Real查询阶段验证

本阶段接续 `80ed8416ee4fcba03519eaa13e10f5d8ed49672f`，正常merge运行记录审核及0043登记Green `c673892ca88fd90f0507ab5087007f4938247f6a` 后，实施起点为 `7060899e7284527bdde25a06335d4aec15eab297`。既有两张事实表和请求修复保留，没有重复实现；完整Feature仍为PARTIAL，不满足完整Gate1或业务合入条件。

已实现上述最小运行契约：canonical执行与独立submission回执同表、数据库活动去重及全局单执行领取、短事务与租约屏障、成功空榜单、榜单失败、补充部分失败、过期中断、安全错误及Team引用保护。新增0043仅在本Feature库应用；0042保持原文件，0043应用后亦不继续改写。Feature当前单一Head `20261010_0043`、47表，运行/候选/观察/ShopSession均0，无测试残留。0043→0042→0043测试保留0042事实；有run时降级在DDL前拒绝。实际数据存在时应用回退保留Schema，不清库。

正式StoredSession适配复用ShopSessionAccessor、819ca33后的HTTP和Signer；类目API使用已确认的level=4、scene=6、default_cate_to_level=2。API权限读事务及内部授权/会话读事务均在平台I/O前结束，返回后复核授权。榜单适配只接受已冻结的业务字符串参数，不猜UI转换。执行开关默认关闭；即使开启，映射未冻结也只整理过期租约，不领取或重发平台任务，没有自动监控或重试。

Real候选列表、详情及运行进度绑定已登记只读API，刷新只读数据库。区分尚未获取、执行中、合法空结果、失败与候选已保存但补充未完成；差评率保留原值和unit，未确认时不换算百分比。类目typed service已绑定正式API，但策略/手动提交页面仍明确不可用；保存策略、定时、百应、资料采集、竞品标记等未接入能力无假成功或Mock回退。原64px缩略图、1496px基础列宽及前端视觉成果保留。

本阶段最终检查（测试平台全部为合成响应，未实际请求平台）：

| 工作目录 | 实际命令 | 结果与边界 |
| --- | --- | --- |
| backend | `.\.venv\Scripts\python.exe -m pytest` | 568 passed，119个integration用例按项目默认选择排除；现有Starlette/httpx弃用警告1项 |
| backend | `.\.venv\Scripts\python.exe -m pytest -m integration tests/integration/test_postgresql_selection_categories.py tests/integration/test_postgresql_selection_runs.py tests/integration/test_postgresql_product_selection.py tests/integration/test_postgresql_product_selection_migration.py` | 43 passed，使用分配的真实PostgreSQL Feature库；不是119项全量PG验证 |
| backend | `.\.venv\Scripts\python.exe -m compileall -q app migrations` | PASS |
| frontend | `pnpm run lint` | PASS |
| frontend | `pnpm run test` | 571 passed，135文件；现有Home/jsdom XHR警告未改依赖 |
| frontend | `pnpm run build` | PASS，包含`pnpm run typecheck`及Real production build；现有大chunk警告 |
| frontend | `$env:PLAYWRIGHT_FRONTEND_PORT='4176'; pnpm exec playwright test --project=mock e2e/product-center.spec.ts e2e/product-selection.spec.ts` | 13 passed，包括此前跨AI导航、四主题、尺寸和原有交互回归；是浏览器Mock，不是Electron |
| frontend | `pnpm exec playwright test --config playwright.selection-real.config.ts` | 1 passed，拦截式Real构建测试，验证正式查询契约、失败及无Mock回退；不等于实际平台或Electron闭环 |
| 仓库 | `git diff --check`、忽略配置和材料核验 | PASS；0042无diff，凭据、原始请求、截图和本机材料未提交 |

真实平台请求次数为0，Feature库仍无合法ShopSession，也未复制生产凭据。此前正式链路两次10条及basic_info成功仅作为请求能力证据，不冒充本阶段入库/页面证据。ca97的正常浏览器已确认短视频/近7天2026-10-03～10-09及当前类目有10条，但工具未取得该次实际Network query，因此仍不能冻结渠道、相对日期、类目及父级全部的转换。最少下一步仍是上节同次正常操作的12个业务参数对照，不要求Cookie或完整cURL，也不重新测试认证/追溯历史错误。

唯一Integration Electron已有Mock视觉/交互记录保留，最终尺寸人工确认尚缺，截图工具超时不能补写PASS。本候选真实请求→入库→API→Real页面、重复获取及真实失败/空结果证据尚未完成。阶段候选交ca97做技术审查及最小证据协调；不能据此合入业务dev或发布。
