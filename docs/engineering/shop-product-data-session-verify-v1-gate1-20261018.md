# 商品数据统一 Session 判断与关键 Verify Gate 1

## 结论与基线

- 分支：`feat/shop-product-data-real-v1`。
- 保留的商品业务/UI基线：`1619f416ee0ca013092fc85ab3219b4fc378b06c`；本地测试准备提交：
  `b7d41c70556c8b025e9cfe4b673cd75d8af8fc94`。
- ca97独立Gate 2及CI四项全绿的共享Green：
  `9878536849fec3d2d2f1dde811e49957abcba13d`；按要求正常`--no-ff`同步，合并提交：
  `9de16ab8f34a6e38e9f7b71010001ffc2a081824`。未rebase、cherry-pick或reset。
- 最终Candidate以正式Handoff的完整SHA为准。本次不是生产发布授权。
- 原商品实现、UI提交与`20261017_0047_shop_product_data_v1.py`保留；没有Schema、Migration、依赖、
  执行开关、运行端口、数据库、Worker或Electron生产代码变化。

## 根因与最小修改

商品消费者仍保留共享Green之前的局部门禁：自行读取Metadata并判断`configured / status / validated_at`
freshness。其结果会把captured、缺少验证时间或陈旧Session返回
`PRODUCT_DATA_SESSION_VALIDATION_REQUIRED`，且把`refresh_required`与公共重新登录语义分开；这既复制状态矩阵，
也没有消费已经审定的权威身份验证和上下文绑定边界。

`ProductDataStoredSessionIO.page`现只做以下调整：

1. 在其独占短Session内先复核generation/lease及授权事实；需要权威身份验证时，HealthService回调先结束
   只读事务，再执行`ShopSessionHealthService.check(force=False)`。
2. 通过`bind_collection_auth_context`绑定同一Shop、抖店平台和Session版本，再释放数据库资源进入商品业务页。
3. 未配置直接拒绝；captured或VALID但验证缺失、陈旧、未来、早于采集时间时至多做一次权威身份验证；
   新鲜VALID复用缓存；invalid/refresh_required不发身份或业务请求；`expires_at`仍只预警。
4. 业务回包后原有Actor/Team/Shop、generation/lease、Session版本及真实Set-Cookie CAS继续保留。
   只有明确`AUTH_INVALID`标记当前版本；新版Session赢得竞争时旧请求不能覆盖。错店、网络、Signer、解析及
   普通业务拒绝不改Session。

未新增商品域Session helper，没有复制公共状态矩阵，也没有为一个业务页追加第二次身份请求。
`PRODUCT_DATA_SESSION_VALIDATION_REQUIRED`类与安全失败码仅为历史回执/Reader兼容保留，当前消费者不再产生。

## 商品专属 Verify

新增凭据无关的商品探针，以独立固定期望直接读取实际实现：

- 三个正式API的method、path、status、response model；关键DTO字段、generation与observation状态；
- 查询默认`page=1/page_size=20`、上限100、固定`sale_type=1/content_type=1`；
- 17项指标的精确code/kind/raw unit；
- `available=0`与`missing/null/invalid`；
- unit3金额精确除100、unit4比例保持分数、大计数不转JavaScript Number；
- 接受时间`2026-10-18T00:30:00+08:00`冻结的1/7/30日窗口及date_type 20/21/23。

PC Real契约使用另一份固定期望核对17项实际消费映射、状态、尺度、请求默认值和冻结日期；期望不从Backend
注册常量生成。`python-runner.py`只增加商品探针登记及`-I`隔离导入路径，公共分类算法、AST检查器、
`contracts.mjs`和`known-differences.json`不变。曾尝试用既有AST登记商品嵌套DTO，但检查器正确拒绝未支持的
本地类型别名；该登记已撤回，没有用known difference掩盖，改由商品运行时探针与独立PC契约覆盖。

七类受控变异均由独立子进程返回非零：API状态、DTO字段、metric unit、零值改missing、金额尺度、比例尺度、
冻结日期。正常样本返回0。探针只构造合成身份、文本与数值，不连接数据库、平台、Signer或Profile。

## Gate 1 实际验证

| 检查 | 实际结果 |
| --- | --- |
| 商品Session消费与Verify定向 | 35 passed；含10种公共准备结果、binder错店/版本、AUTH_INVALID、非认证失败、7类负向变异 |
| 商品解析/Connector/Collection/Schema/共享Session组合 | 154 passed |
| Backend完整离线profile | 1042 passed、441 integration deselected、1条既有Starlette/httpx deprecation warning |
| PC商品定向单测 | 15 files、136 tests passed |
| PC完整单测 | 169 files、920 tests passed；未启动Vite服务 |
| PC lint / typecheck | 均exit 0 |
| Python compileall / `git diff --check` | 均exit 0 |
| Node 24.19.0 / pnpm 11.25.0默认`verify` | exit 0；28 known、0 new failure、0 stale；商品/客户端契约8 tests passed |
| `verify --strict` | 预期exit 1；仅同一28项failure、0 stale |
| `verify --full --only=backend` | exit 0；1042 passed、441 deselected；28 known、0 new、0 stale |

本机安全报告位于ignored `.codex/product-data-session-verify-v1/`：

- 默认：`e7f6d67819e3d3cf8973c490e09c7302937857fb3adb9aba9ac6c210db123986`。
- strict：`fdde04a6ae02ef49bb6f580b4ad9ae0e6fe6a74b5c711cdc035dd3a5d26002bd`。
- full Backend：`384cd85caf50bfd638bc9405abdb86e5195aa4c2342b26d58341b6c8c77b3403`。
- `known-differences.json`仍为
  `4ddacab88bc5a67737a024138ef9f487d6d536b48944092c46ab8ac79258c86b`，无diff。

第一次默认Verify从系统Node 20启动，pnpm 11在运行检查前因缺少`node:sqlite`退出；随后使用工作区已配置的
Node 24.19.0原样重跑获得上表正式结果，未安装或升级依赖。一次带`--`的PC商品筛选命令被Vitest解释为全量，
得到920项全绿；之后用精确目录参数另跑商品15文件/136项全绿。二者均未启动服务或访问平台。

## 未覆盖、回退与 Gate 2

- 未连接Feature、Integration、Main或生产PostgreSQL；未执行或校验Migration/0047、PG集成测试或数据回滚。
  `test_product_data_session_postgres.py`已按新语义更新，等待原CI disposable PostgreSQL覆盖，不冒称本机通过。
- 未发真实平台/Signer请求，未启动Backend、Frontend、Electron或Worker服务，未运行原生Electron、安装包、
  容器、部署、生产smoke或人工平台闭环。
- 完整离线profile按既有声明未运行会绑定端口的
  `test_douyin_signer_runtime.py`与`test_notification_webhook_e2e.py`，两项为NOT_RUN。
- 回退只需正常回退本候选的消费者、测试、Verify登记和文档；没有数据库、Migration、配置或凭据恢复动作。
- ca97 Gate 2需独立复核共享接口真实消费、无事务跨身份/业务I/O、错店/版本/CAS/失败分类、默认/strict/
  负向Verify及完整Backend结果，再决定是否合入dev。不得自行合dev/main或发布生产。
