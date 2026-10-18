# 商品数据真实接入 V1 技术验证与交接

## Green a6同步与最小复验

Owner已独立核远端dev为 `a6df9ac43b0987b68bd13313ab40d2aeca84c63d`，精确CI `39024117248/attempt1` 的backend、frontend-real-build、container-runtime、verify-offline四项全部success；旧545不是采用基线，未消费main部署merge。原Feature正常no-ff同步，merge `891116750157ab5b12e83e1da6bdbfc646d66ec5` 的双亲为d3c04dae与a6df9ac，无冲突、无历史改写。运行业务树相对d3逐字一致（Backend、frontend/src、Mobile、Electron、Worker及锁），0047 blob仍为 `5128cb64a5bf3a4913b55ae0147c7c57bced0fe6`。

合后正常 `pnpm verify` quick-offline exit0/21.38秒：9 Node负测、2 Python AST、4 PC/Mobile内存客户端观察及权威/消费方静态对照完成，28项精确已知未修复、0新增、0stale，私有包管理器安装树为空。known-differences文件SHA256 `4DDACAB88BC5A67737A024138EF9F487D6D536B48944092C46AB8AC79258C86B` 保持，不将例外写成缺陷已修。实际Node24.19.0、pnpm11.25.0，声明pin11.19.0不改；前端vue-tsc/eslint复验通过。精确最终候选Real production构建与资产hash附本机回执。

首次Verify在入口执行前被workspace布局元数据拒绝，外层pnpm exit1，不计测试失败或已运行。确认7d55自己的node_modules/虚拟store均非他人junction后，以原store按offline/frozen-lockfile/ignore-scripts规范对齐，复用202、下载0；锁SHA256始终 `CDF9803569D82DA85EE9D71D3AA02641AEF73F90EB884705073E9E522A70E796`。未关闭verify_deps_before_run、改pin或在线安装。首次设置阻断与后续正常报告分别保留在Owner ignored `green-a6-initial-dependency-gate.json`、`green-a6-verify-default.json`。

本次只做Green工程同步与元数据交接。d3的979 Backend、62 Feature PG、911前端/181定向及单位链路证据按相同运行字节复用，未冒称重跑。未执行verify --full、PG/DDL、平台业务/Signer、容器、原生或安装包；不重采、不改别名/字段、旧unit_complete_rows或真实样本。ca97已报告d3的原三窗178/229/344、12767原值及单位、12筛选/9排序与新增10 Integration PG/27表保护通过；这是其独立既有证据，不是Owner本轮动作或新候选完整Gate2。新增原生确认仍受工具限制，不据此补写Gate2B或发布通过。新候选交ca97精确增量复核，Feature不合dev/main、不释放0047或发布。

## d3阶段官方单位核定与比例区间接线

沿392候选追加，不改原预算修复。Owner已独立从官方商品列表HTML追到商品微应用1.0.0.3672、实际路由chunk363/表格适配37603、cell_info当前值解包33017、EUE导出54761及实际formatter nF；商品列只覆盖比例precision，没有覆盖price/ratio倍率。确认3金额unit3除100为元、4比例unit4保原分数且展示乘100%。不只采信父页4977枚举；公开资源SHA、完整调用链及三成功窗口21项非零公式见shop-product-data-unit-contract-evidence-20261017.md。

最小运行修改：Backend固定17指标核定尺度，金额规范值只改Decimal指数保全精度；原JSON/DB值不换单位。当前GET unit_verified与coverage反映尺度已知，四比例范围按原分数Decimal在全量SQL执行，金额/比例排序复用原NUMERIC/稳定缺失最后。前端在原typed mapper保raw元数据，固定十进制文本位移与BigInt做最终2位展示，四比例UI1%精确发送0.01、0.29%发送0.0029；复用既有验证和组件，无新通用框架。17映射/别名、旧兼容四列、所有不支持维度及失败保护保持。

request_contract、metric_contract、source/series hash、Model及0047逐字不改，原三代178/229/344共751快照不因新契约被隐藏。旧unit_complete_rows=0不回填，当前可核定单位与历史采集覆盖分开；真实读取新候选751项的集成复核由ca97完成，不将本机测试冒称其已加载新代码。

Gate1实际验证：接线前Backend三窗口3项失败、Frontend三窗口展示及4比例提交共7项失败均保留；接线后Backend默认979项、真实Feature PG62项、Frontend定向22文件181项及全量166文件911项、全前端eslint/vue-tsc通过，0失败/错误/skip。包含三窗口7指标独立公式、超过28位Decimal/安全整数精度、最后位half-up、零/未知/错误unit/负向、四比例[min,max)精确边界与分页、九区间全量组合、3金额排序、旧别名/无效维度、历史覆盖不回填及392预算回归。前端新FilterBar测试首轮缺测试尺寸token失败的报告保留，按既有测试初始化补齐后整组复验，不改生产主题。既有Starlette弃用和全量jsdom本地XHR警告如实保留，不升级依赖或称无warning。

PG仅精确已登记Feature，前后单一47、四表0行、最小角色五高权false、五执行/调度开关false；明确排除原空表降级1项，不重跑DDL。Owner只额外读取无认证官方静态资源及ca97既有白名单记录，无新增平台业务取数/Signer、Integration/生产写入或客户端操作。新精确候选/Real构建回执另附；单位与九区间代码Gate1已完成，但新候选Gate2/原生页面、生产验收与Release未据此通过。

ca97曾提出名称语义风险，随后与Planning核对原人类已明确批准的别名/映射，已撤回强制更名及由此阻塞的意见。本候选保持“真实订单”→net_pay_cnt、“异常订单”→pay_cnt_exclude_refund，原Tooltip明示官方净成交订单数／退款后成交订单数（支付时间），不等同发生退款订单或风控异常。Root本次一手meta核对与旧白名单一致，两项index_tip均空，不能从单样本差额推算法。可选更名需后续明确人类选择，不属于本次单位候选的停止条件，不替换原值或重采。

## 392阶段采集上限反馈返修

ca97既有安全观测表明：915候选的正式1d代 `9b34af56-d37a-48d7-b1f8-00f526bbbe04` 已18页/178件原子发布，正式GET178、同key回读无新增平台请求。7d代 `4c695088-4432-4d33-b015-54de4bc5ba26` 首HTTP200、整数st0，严格parser成功返回page1/10行、total229；所需23页超过首轮20页/200件，Service在记录进度前主动停止，故旧回执0页/expected_total=null。根因是受控预算保护及其反馈不清，不是响应格式、日期未就绪、签名、传输或Session无效。旧7d失败不能记完整通过，后续批次与30d仍以ca97实际结果为准。

最小返修沿原Feature追加：collector/Service预算分支使用独立安全码 `PRODUCT_DATA_COLLECTION_LIMIT_EXCEEDED`，Executor保持collection_coverage，在原失败live-lease CAS中通过既有expected_total填入安全可表示的已知正整数；保留已有总数，不增加已接收页或发布部分行。INTEGER范围外仍能保存明确失败而总数null，不因诊断溢出丢失终态。其它错误不传总数，错lease/终态不得被迟到失败改写。

前端原StatusTag/Tooltip明确“超出采集上限”、可用总数及“本次未发布，已有成功数据保持不变”，未知不补0。旧PLATFORM_RESPONSE_INVALID不倒推改码；同key只读原失败，不自动重试。未改parser、请求参数、默认预算/并发、实际环境配置、0047、Model/DTO字段、HTTP资源或调度框架，无Electron/Worker/Mobile变化。3金额/4比例及4比例区间仍未完成，不由178条原值推断单位。

实际验证：修订前预算3项失败，前端正确Tooltip stub下2项失败/6项通过；首轮stub未命中组件导致额外断言失败的原报告也保留。修订后Backend默认967项、解析/连接器/有限采集定向76项、真实Feature PG53项、Frontend19文件141项、eslint/vue-tsc均通过，0失败/错误/skip。PG包含错误/终态lease CAS、229总数与0已接收页、INTEGER溢出安全、既有总数保留、正式回执GET/同键回放及旧事实保护；合成平台与真实PG证据，不冒充新平台请求。原空表降级1项明确排除，不重跑DDL。

Feature前后审计仍为精确control_center_feat_shop_product_data、最小角色五项高权false、单一0047、四表0行、五执行/调度开关false；47 blob `5128cb64a5bf3a4913b55ae0147c7c57bced0fe6` 保持。Owner没有新增平台/Signer请求或连接Integration/生产，未操作客户端。原915/80d/591、真实成功与失败、旧构建和本机材料全部保留。精确新候选及Real构建回执另附Owner ignored材料，供ca97增量Gate2，不将此返修标全产品/生产通过。

## 915阶段核心单位待核与提示修订

当前是基础链路/原值模式，不是完整商品数据交付：17项核心的10项计数可显示，3项金额及4项比例的官方显示尺度仍待同店、同商品、同冻结窗口对照；九项区间仅5项数量可用，4项比例仍禁用。须在证据取得后由7d55在原Feature完成最小映射、格式化、百分比区间接线与回归，才可核销这些核心项；不等单位而停止其它链路，也不把原值入库或禁用行为标为全功能PASS。

完整已交付/未完成清单见同目录 `shop-product-data-real-v1-acceptance-checklist-20261017.md`，包含1/7/30冻结窗口与日期示例、17名称/code/unit、9区间、默认20/页、全页原子发布、幂等/失败保护及Integration/生产分别核销项。特别要求执行前核实际MAX_PAGES=20，而不是默认100；health不得从至多一次自行扩成每页/每窗口一次。未支持的分组、自定义采集、其它切片/平台和自动删除不扩展。实际环境进度、操作预算、Gate2/Release由规划/ca97/Main本轮记录统一协调，Owner不自行跨环境或操作桌面。

发现并修订一处前端真实文案缺陷：统一指标Tooltip仍含“真实接口尚未接入”，与已交付的Real链路矛盾。修订提交 `8b6803681940836bbec1e1eab114830dccd30a22` 只改为“数据可用性以当前数据源为准”，保留演示警告、官方口径与单位待核提示，不开放单位/筛选、不改API/Backend/0047。先加定向测试复现1失败/4通过，再最小修订；19文件138项定向通过，eslint/vue-tsc通过。前后Junit均在Owner ignored材料保留。

8b68036精确Real构建20.18秒通过，商品chunk `ProductDataPage-ZxCSYUpJ.js` SHA256 `EC9B39020D594B3EFF28C56B0F43938DFED38036A7D81A33EC2DCECB1C041B2E`；最终含交接文档的候选另附精确回执。Backend及47逐字不变，复用下节958单测/46 Feature PG证据，不冒称本次重跑数据库或真实平台。下述80d/Green157及原591记录、失败报告、样本、旧构建和未覆盖项完整保留。

## Green 157 同步复验

当前目标基线为 `157f9400814aabad574b3d7860ba8bb8a6f00c3b`。Owner已核远端dev与精确CI `39002413981` 的headSha一致，Backend、Frontend Real build、Container runtime三项success；这不是新Feature候选的CI结果。原分支无冲突正常no-ff同步，merge `17afc7e8d98a7b40102b4c31ee41099c59d22cfb` 的双亲为原5915009与Green157，591/c448/af6历史及全部本机材料保留。

复验提交 `576cb9be264b889a654c8e5a8025f7b9dc1a7307`。本轮仅新增2项真实Feature PG回归，确认HealthService新可选before_platform_io回调默认为None时，不回滚调用方已经flush的写入：缓存路径不新增提交/回滚，强制成功验证保留原Accessor提交语义。商品API、执行器、Session适配、来源/单位契约、前端商品运行代码与原591逐字相同，无需业务兼容修订。新运行差异仅为已核Green的经营恢复与共享Session增量，未追加功能。

| 同步后验证 | 实际结果 |
| --- | --- |
| Backend默认单测 | 958通过，0失败/错误/skip；`green157-backend-unit.xml` |
| 真实Feature PG | 46通过，0失败/错误/skip；含新增默认事务2项、商品API/权限/发布/Session与独立双连接并发；`green157-postgres.xml` |
| Frontend定向 | 商品、Product实体、经营恢复和共享列表密度共19文件137项通过；`green157-frontend-targeted.xml` |
| lint/typecheck | 全前端eslint与vue-tsc均通过 |
| Real production构建 | 576cb9b干净源码，18.36秒通过，86个JS；`.codex/product-data-real-v1/real-build-576cb9b`。商品chunk `ProductDataPage-6CUqSxQ0.js` SHA256 `D92E971AEFC95012E66BDF94AF75E3005E4AD77A58CB8016100ED9FAF7E8B7B5`；合入Green导致共享chunk引用变化，不能沿用旧A7哈希。商品Fixture标记0，inert预览引用1如实保留。 |
| DB与文件护栏 | 前后审计精确Feature库、最小角色五项高权false、单一47、四商品表0行、五执行/调度开关false。47 blob仍为`5128cb64a5bf3a4913b55ae0147c7c57bced0fe6`，本轮不执行DDL；原空表降级闭环作为旧证据保留，明确排除该1项而非标为本轮通过。 |

PG命令在Owner backend目录显式选既有5个product_data PG文件、`-m integration -k 'not test_new_empty_tables_downgrade_and_upgrade_keep_existing_marker'`，没有运行他域Integration夹具或写其它库。未连接Integration/生产，平台/Signer预算仍0，没有新服务、窗口或安装包；不要求用户重新登录或提供Cookie。下述原Gate1与未覆盖项保留，新的精确候选交ca97增量Gate2复核，不把旧Gate2A或新Green视为商品真实闭环/发布通过。

## 5915009 初次 Gate 1 记录

Owner 7d55，2026-10-17，分支 `feat/shop-product-data-real-v1`。本里程碑完成基础手动采集、入库、查询和前端接线的Gate 1技术自检，交ca97独立Gate 2。真实平台、Integration环境和新前端人工观察未覆盖，不表示商品数据完整真实闭环通过、Green或发布授权；不再要求用户重复登录或窗口测试。

运行实现提交为 `c448deaabe5a68b4a50146f4928022fb26bf1385`；本交接记录随Feature追加，最终候选HEAD以Git及交接回执为准。目标Green `origin/dev=bef7093b755cea60fda55bbcc6177b5723d4738a`，提交前ls-remote再次一致。沿原分支正常no-ff保留UI `af6b737281c16e469fdc6300f80cdfb40cb5c981` 和c301，正常同步Green；不消费ca97未推送治理HEAD，不改写共享历史。

## 实现范围

- 原生1/7/30、基准sale1/content1、固定74字段请求、17核心原值。跨日重放返回原冻结日期。0商品包装未证实，明确拒绝而非发布假0。
- 有限全页校验、完整代原子发布、稳定Shop商品身份、同店/同序列FK、单调序号与lease fence。失败、过期、撤权、较旧代不覆盖成功代。没有扫描、自动重试、每日任务或TTL。
- `GET /api/v1/product-data`、`POST /collections`、`GET /collections/{generation_id}`。当前人员/Team模块/Shop实时校验；共享事实与本人运行回执分开。SQL全量组合筛选、稳定排序后分页，默认20。未知参数/未支持维度不静默忽略。
- 平台HTTP在DB事务外，当前Session通过Accessor解密。首版只消费已验证且新鲜Session，陈旧/captured明确要求现有验证入口，不自动身份请求或登录。真实Set-Cookie走HealthService/加密版本CAS，迟到结果不能覆盖新版本；业务拒绝不标认证失效。
- 前端typed Real只用正式三个资源，不回退Mock；显式单店更新、同帧防重、未知提交同key重试、GET失败只重读回执、上下文迟到保护。金额3/比例4显示单位未核定，保留原值/原unit，不换算；精确整数和ID不经Number损精度。分组、自定义、其它售卖/载体及相关未核定单位操作禁用，旧偏好/Mock保留。

契约同步：Backend04/05/10/26、Frontend05/18；既有来源提案和离线样本不改写。Backend只复用既有HTTP/Signer/Session边界；共享 `session_query` 抽取保持选品原行为。无Worker、Mobile、Electron改动，无新依赖或锁文件改动。

相对Green仍有两条历史Shared差异：`frontend/src/shared/ui/list-density.ts` 与 `frontend/src/shared/components/list-density.spec.ts`，为原UI正常消费的141 Radio紧凑修补，逐字继承af6，分别blob `b1f4f11885defbe0ba2b677435a7c7498b062010` / `15c550a25cb41ad6f627fa279da64f5015ee6905`。本轮没有新Shared/Entity修改，但不将“相对Green无Shared diff”写成事实。

## 资源与数据库

ca97登记的唯一active Slot47：`20261017_0047_shop_product_data_v1.py`，revision `20261017_0047`，down `20261015_0046`。已应用47，不改写已应用迁移；本次运行接线未再改Migration。

唯一Feature DB `control_center_feat_shop_product_data`，角色 `control_center_dev_user` 五项高权标志均false。35433是共享集群隧道，不是独占实例；每个PG夹具/迁移/降级前严格核完整库名、角色、登记入口，SQL再次确认current_database。测试护栏只允许Owner此Feature，不能直接复制其连接到Integration或以其它DB绕过；ca97的Integration动作仍按自身登记和目标护栏执行。

正式受保护 `backend/.env` ignored且不进Git，未输出或复制连接串。8102/4177归7d55，本轮无监听、新服务或Electron；不碰81a1资源、窗口、Profile或共享stash。结束只读审计：单一47，四张商品数据表均0行；product data、选品执行/调度、经营执行/每日五个开关均false。仅虚构测试数据按事务或本次稳定UUID收尾，不清业务资料。

## 实际验证

| 检查 | 实际结果 |
| --- | --- |
| Backend默认单测 | 947通过，0失败/错误/skip；与PG组分开。根目录执行 `backend/.venv/Scripts/python.exe -m pytest backend/tests -m 'not integration' -q --tb=short` |
| 精确Feature PostgreSQL | 45通过，0失败/错误/skip；backend目录显式选5个product_data PG文件，`-m integration`。包含约束/精确NUMERIC/0与未知、同Shop/同序列FK、无Team幂等、原子发布、失败保护、撤权、迟到序号/lease、SQL范围排序分页、API/匿名拒绝、Session版本/Cookie及3项独立双连接并发。不是SQLite或平台Mock的PG替代。 |
| 迁移 | 新空库先到46再47；空新表47→46→47通过，旧User标记前后保留，结束移除本次标记。含新业务行的降级保护有离线探针，未冒称完成真实有数据降级尝试。 |
| Frontend全量 | 162文件、856项通过；最后定向11文件93项通过，包括typed DTO/原值、不可用维度、同帧防重/同键恢复/只读重试/迟到UI保护及旧UI回归。 |
| Frontend静态 | `vue-tsc --noEmit -p tsconfig.app.json`、`eslint .`均通过，使用现有node_modules入口，没有pnpm引导升级。 |
| Real production构建 | c448dea干净源码，`VITE_API_MODE=real vite build --mode production --outDir ../.codex/product-data-real-v1/real-build-c448dea`，23.55秒通过，86个JS。未覆盖旧产物，未打包Electron。 |
| 静态Real边界 | 商品Fixture标记0、正式API标记1个文件；仍有1个inert `productDataPreview`参数引用，factory生产条件不导入Mock，不能将其命中隐去。 |
| Git与隔离 | diff --check通过；全部新增文件逐项审计；.env/.venv/.codex/本地覆盖/草稿 ignored，未暂存。原样本、旧候选和旧构建保留，无reset/clean/强推。 |

原始Junit和构建在Owner ignored `.codex/product-data-real-v1/`。最终报告 `backend-offline-full.xml`、`postgres-final.xml`、`frontend-full-final.xml`、`frontend-targeted-final.xml`；原失败/0用例报告保留。初始PG导入/FK夹具错误、API错误结构断言、Vitest hook误返回Mock函数均修正后独立复跑，不修改通过标准。全套前端出现jsdom本地XHR警告，Backend有Starlette兼容弃用警告；测试均按实际结果通过，不宣称无warning，不为此升级依赖。

Real商品chunk `ProductDataPage-phYa2Fwm.js` SHA256 `A7B644CACC4D6F814881F9333575EDBA31308336865F2283BDB56852B28FC2B0`，仅构建核对材料，不是安装包或正式发布产物。

## 未覆盖与停止点

本轮真实平台和Signer请求均0。新鲜74全页1/7/30、真实0商品包装、金额/比例官方显示尺度、真实大店耗时、Integration HTTP/数据库、浏览器Real集成、新UI原生观察和用户人工验收未覆盖；历史单页146总数不等于已采完146件。原UI确认不移作新Real验收。

分组权限/关系、自定义日期、其它sale/content、自动每日、通知与历史删除未实现或未定，不隐式启用。负raw unit在解析可保留为invalid，但当前存储只接受非负unit；若实际出现则失败保留旧代，不改应用过的47或伪造原值。

ca97先独立审查此精确候选及未覆盖项，再按现有流程安排Gate 2；必要的新平台动作须另有明确授权，不能借本记录发起。禁止Feature自行合dev/main或生产发布；不新增窗口、不要求重复登录验收。

回滚采用关闭新手动入口/回退兼容应用，保留47及事实。四表非空不得降级，不能以drop/清库或复装客户端作回滚。正式包或生产部署均不在本轮交付范围。
