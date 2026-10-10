# 选品前端验收状态与真实接入资源

2026-10-10，Integrator ca97，Feature Owner 81a1。独立数据库和新 Migration Slot 已分配；请求链路成功证据可复用，真实持久化闭环尚未完成。本轮不发布生产。

## 提交与前端验收

| 项目 | 精确状态 |
| --- | --- |
| Green 基线 | `b34e43cb90356e03d2f793c4146c6775a11f5ab3`；资源登记前 ca97 dev/origin/dev 一致且 clean |
| 初次核对 Owner | `C:\Users\Administrator\.codex\worktrees\81a1\中控台`，`feat/product-selection-frontend-v1`，HEAD/origin 为 `819ca33ba6548030e418320c6bb80ba046beb842`，clean；此后 Owner 的接入准备修改继续保留 |
| 资源同步 | ca97 登记提交 `675016769ba0b55f8ed42c15e7500b0c6291f968` 已推送 dev；Owner 正常 merge 后为 `0c75ef05e36e6c7f5ce8137a6bd81e4102f7e515`，819ca33 与最终前端树均保留，不将该文档 merge 当作业务 Gate 通过 |
| 前端最终候选 | `06bd03c0fa61b00251063e21350cd0cc5445afe5`；Gate 1 有完整 Handoff，含 lint/typecheck、41 定向单测、13 Mock E2E、Real build |
| Integration 返修复核 | 06bd03c 独立 lint/typecheck/Real build、41 单测、3 定向 Mock E2E、diff check PASS；前一 91461d4 Review2 返修及 Real 无回退证据保留 |
| Electron | 唯一既有开发窗口，5180 的 06bd03c Mock 快照；32 条演示候选。已有交互/主题确认保留，尺寸收尾记录仍为等待最终人工确认，不用浏览器截图补写 Electron PASS |
| dev 合并 | 06bd03c 与 819ca33 均不在基线 dev，未合并，无 Merge Commit；资源登记不代表业务合并或 Green 新功能 |
| 诊断补丁 | 819ca33 是 06bd03c 的直接后续，仅请求层、9 项定向测试及 Backend 说明；两提交 Frontend tree 均为 `0cfd65b3eb7573a2ba5be6b9a7cef08977f85e84`，Electron 树亦相同。定向审查 PASS，不等于完整 Gate 2 |

前端仅确认界面及 Mock 交互，不证明真实采集、持久化、策略保存或调度完成。恢复 Real 后必须没有 Mock 残留/回退，未接入部分如实不可用。

## 已确认取数事实及未知边界

正式认证来自 HuanYu 数据库 ShopSession v1，平台 shop_id `243321624`；链路为 Accessor → 819ca33 DouyinApiClient → 既有 Signer。两次榜单均 HTTP 200、整数 st=0、10 条，basic_info 成功且商品身份匹配。签名 Cookie 与实际 HTTP Cookie 一致，签名后复用同一请求并保持业务 Query 编码。本轮不再追加平台请求。

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
| 初始化及现状 | 初始0041/44表已核验；Owner执行0042后，Integrator最新只读核对单一 `20261010_0042`、46表、候选/观察/ShopSession均0、两表模型差异0、角色权限仍最小；未执行共享环境迁移或平台任务。Owner `.env` Git Ignore PASS |
| HBA | 仅新增本 Feature DB + 应用角色 + `172.17.0.1/32` SCRAM 规则，位于 reject 前；解析错误0，reload，无服务重启；其他规则不变 |
| HBA 备份 | 持久化数据卷中的 `pg_hba.conf.before-product-selection-20261010T112247Z`；SHA-256 `4d6671e093bc9fcb1665d207a08ade58806c4a19e7d34b200ea686080ca1eb7a` |
| Head 与 Slot | Integration/生产已核验单一 `20260924_0041`，旧0041 Slot released；本 Feature 唯一 active Slot 继续覆盖已应用的0042及追加reserved `20261010_0043_product_selection_runs_v1`（revision `20261010_0043`，down `20261010_0042`）。不改写0042、不另开活跃Slot；追加文件由Owner编写，完整候选一起验收 |
| 端口 | Owner Backend 8101，Frontend 4176 strictPort；只登记未启动。Integration 保持8100/5180及唯一 Electron，真实平台由 ca97 协调 |
| 凭据 | 复用 Owner 本地忽略配置中的既有应用角色凭据，仅更改目标数据库；不得回传完整连接串，不能继续使用旧 Availability 库 |

81a1已完成两表、事实服务和只读API，不重复安排开发。部分候选80ed841对团队引用保护的返修复核PASS：Integrator独立65项定向测试通过，纯内存探针确认引用检查包含候选；Owner的21项PG及409/204用例已审阅，未宣称Integrator独立重跑。整体仍PARTIAL，未合入dev、未释放Slot。

## 手动运行技术决策

业务专用run方案允许实施，由81a1将正式DTO、Model、Service/API和本节约束同步到Backend契约。run保存Team/发起User/请求Shop（RESTRICT）、submission_key、版本化白名单条件及明确日期、状态/阶段、实际结果计数、安全错误和租约。只增加本业务必要结构，不重做两张事实表。

- `(team_id, created_by_user_id, submission_key)`保证回执幂等；相同原始用户条件必须返回原run和已冻结日期，不能因跨日重新计算相对日期而误判409或再次请求。相同key不同用户条件409。活动同Team/Shop/规范条件由PostgreSQL部分唯一约束去重，处理特定唯一冲突返回同一run，不把刷新当提交。
- pending只来源于明确手动提交。复用Backend现有lifespan和有限 `to_thread` 执行模式，短事务领取、平台I/O在事务外；模块执行开关默认关闭，复用现有配置体系，不复用经营/AI队列，不增加定时或自动平台重试。
- lease_id/有效期须通过数据库条件更新或行锁，与本次事实写入、计数及last_run_id关联处于同一短事务。不能只在Python中检查租约后由现有FactService独立commit，留下检查/写入竞态；复用现有服务/Repository，不另造事实写入实现。每次HTTP前和事实写入前复核当前User/Team/模块/Shop授权及启用状态。
- 无候选的合法成功空列表记录succeeded及真实0计数；取得榜单前失败记录failed/安全阶段，未知计数为null；候选保存后补充缺失或失败为partial，旧有效事实保留。计数明确指取得、有效写入（包括幂等更新）及补充结果，不把未取得值填0，不将去重更新数冒充新增候选数。
- running租约到期记录interrupted且保留事实，不自动重发结果未知的请求；旧执行者不得续旧租约或写回。权限撤销/停用后停止后续HTTP及事实写入，仍由有效执行租约安全结束run并记录固定安全原因，不能永远留running。关闭时不得把取消协程当作已停止线程/HTTP；依靠有限超时及租约屏障挡住迟到写回。
- Observation.last_run_id只表示当前有效事实的来源，写入前校验run的Team/Shop一致且满足既有新旧执行排序。历史run保留条件、状态及计数，不承诺不可变商品/逐项失败快照；旧run关联被新事实替换后，UI不得把空关联列表说成当时没有候选。不为此增加第四张Item表。
- 继续既有Actor/Module/Shop Scope，普通读取当前Team/授权Shop，超级账号创建需明确Team。Team引用检查纳入run，覆盖只有空榜单/失败run时的409。平台业务码保留安全int/string原类型；无Cookie、Token、签名、完整URL、原始响应或任意异常消息进入run、日志和错误详情。
- 0043只增加run及必要关联/约束；0042文件保持字节和逻辑不变。0043降级仅允许可重建Feature库、run为空，保留全部0042事实；有run则先拒绝，不执行破坏性DDL。正式数据存在时应用回退保留Schema，不自动降级或清库。

Gate 1须覆盖跨Session提交/领取、回执丢失及跨日幂等、成功空结果、失败前无候选、basic_info部分失败、执行中撤权/停用、租约过期及迟到写回、刷新零平台请求、只有run的Team引用、0042事实保留与0043降级拒绝。

## 最小请求映射与会话边界

现有材料只证明成功样本的实际字符串参数。正常罗盘页面尚无可用模式/快捷日期对应证据，不由接口路径或Referer推断短视频模式，也不从2026-10-02至10-08推导所有“近7天”。可继续纯DTO/状态/数据库与Real读取适配；未冻结条件的执行选择需明确不可用。

最少补证据为既有合法罗盘页面的同一次“短视频＋近7天＋当前类目”正常操作：仅登记所选模式、页面明确日期、12个白名单业务参数及分页。若父级“全部”仍不明确，再做一次单因素类目操作；不覆盖所有周期/品牌/价格、不再做认证成功测试。优先复用已保存页面证据，无Cookie/cURL交接。自定义价格、其它周期、首次上榜及未确认单位继续不支持。

Feature库ShopSession=0，不复制生产Cookie，也不增加跨库认证桥或身份模块。Feature网络测试需本环境正常授权的Session；最终候选Integration真实闭环由ca97使用Integration正常登录会话、隔离Signer及8100/5180验证，Owner不得切库写Integration。若已有Integration Session不可用，只请求一次正式店铺登录；生产只读旧证据不冒充新候选入库闭环。

可以继续固定路径解析、错误分层、适配/DTO和离线测试；真实请求→Feature/Integration入库→正式API→Real页面及权限/幂等验证在新的完整 Gate 1/2 候选上完成，再走 Green dev 与适用 Release Gate。
