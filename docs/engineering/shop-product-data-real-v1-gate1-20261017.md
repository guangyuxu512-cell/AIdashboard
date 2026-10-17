# 商品数据真实接入 V1 技术验证与交接

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
