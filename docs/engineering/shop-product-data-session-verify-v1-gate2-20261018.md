# 商品数据统一 Session 与关键 Verify Gate 2

## 结论与集成提交

- Gate 1 Candidate：`5f06e12b5ca2a38bb77b0c66757f67a7c8889a49`，远端
  `origin/feat/shop-product-data-real-v1` 与工作树一致且干净。
- Green 基线：`9878536849fec3d2d2f1dde811e49957abcba13d`。
- Integration 以 `--no-ff` 合入，merge：
  `11e396187638b1e71b6ec94eaca657899d25b266`；合后 Backend、Frontend、
  Mobile、Electron、Worker、Verify 与 Candidate 运行字节一致。
- Gate 2 接受本候选。精确 dev Green 仍以本记录提交后的 CI 结果为准；本记录不授权
  main、生产发布或真实平台追加请求。

## 独立审查

- 商品消费者删除旧的 `VALID + validated_at` 局部门禁，改为调用公共
  `ShopSessionHealthService.check(force=False)`，再由
  `bind_collection_auth_context` 绑定 Shop、平台和 Session version。
- 新鲜 `valid` 复用缓存；`captured`、验证时间缺失／陈旧／未来／早于采集时间时至多进行
  一次权威身份验证；`invalid` 与 `refresh_required` 不发身份或商品业务请求；
  `expires_at` 只预警，不作为本地硬拒绝。
- Owner 专有只读 Session 在权威平台调用前显式结束读事务；商品页 HTTP／Signer I/O 不跨
  数据库事务。业务请求后重新复核 generation、lease、授权上下文和 Session version。
- 只有明确 `PlatformAuthenticationInvalidError` 以 CAS 标记当前版本 invalid；错店、网络、
  Signer、解析和普通业务拒绝均不把 Session 误判失效。响应 Cookie 更新仍走原版本化写入，
  新版 Session 胜过旧在途请求。
- 商品 Verify 的期望独立于运行常量，覆盖三个 API、关键 DTO、17 指标 code／kind／unit、
  zero 与 missing/null/invalid、金额／比例／大整数精度及 1／7／30 日冻结窗口。公共分类算法、
  `contracts.mjs` 与 `known-differences.json` 未变；后者 SHA256 仍为
  `4ddacab88bc5a67737a024138ef9f487d6d536b48944092c46ab8ac79258c86b`。
- 本增量没有 Schema、Migration、依赖、Electron、执行开关或运行端口变化。既有 0047、
  商品数据业务和已确认 UI 原样保留。

## Gate 2 实际验证

| 检查 | 结果 |
| --- | --- |
| Session／Health／商品解析与契约定向 | 合后 `176 passed` |
| Frontend 商品契约 | `1 file / 4 tests passed` |
| Backend 完整离线 profile | `1042 passed / 441 integration deselected / 1 existing warning` |
| Frontend 完整单测 | `169 files / 920 tests passed`；既有 jsdom XHR stderr 不影响通过 |
| Frontend lint / typecheck | 均 exit 0 |
| Python compileall / `git diff --check` | 均 exit 0 |
| 商品 Verify 受控负向变异 | API status、DTO field、metric unit、zero/missing、amount、ratio、period date 七类均非零退出 |
| 默认 `pnpm verify` | exit 0；28 known、0 new failure、0 stale |
| `pnpm verify --strict` | 预期 exit 1；同一 28 项 failure、0 stale |
| `pnpm verify --full --only=backend` | exit 0；1042 passed、441 deselected；28 known、0 new、0 stale |
| 合后默认 `pnpm verify` | exit 0；28 known、0 new、0 stale |

预合并安全报告 SHA256：

- 默认：`d1778abd9670e89bfda122b2a074a99c748abb360b6bd8097d479b635268a2d0`。
- strict：`0d8edf4908767c4807f6523903bdeb9bc681cb10ad48e39ed64c7761365661ff`。
- full Backend：`63cfba096c804438c7ffaf2b098620af1735a8d1927362010015b0aa457bb649`。

合后默认报告 SHA256：
`2ebbae772fd086ed64145466ead66982f85148f61e03ac36f5e8a1fe4460fd85`。

一次预备诊断直接调用了 `node scripts/verify.mjs`，没有使用仓库声明的 pnpm 入口，结果没有被
采纳为 Gate 证据；随后按正式 `pnpm verify` 入口在 Candidate 和合后各自执行，均稳定得到上述
28 known／0 stale，独立客户端探针也确认四项运行时 known difference 均被实际采集。没有为此
修改代码、分类器或例外清单。

## 复用证据与边界

- `control_center_integration` 已在此前商品数据 Gate 2 完成受保护 pre47 备份、单一
  `20261017_0047` 升级、46 项真实 PostgreSQL 验证及旧 23 表／既有商品事实保护；详见
  `shop-product-data-real-v1-gate2-20261017.md`。本增量不改 0047，因此不重复迁移或重写事实。
- 既有 HuanYu 1／7／30 日正式采集、SQL／API／Real 展示、指标尺度、筛选和已确认原生界面
  证据继续有效。本增量没有 UI 字节变化，不重复要求人工视觉验收。
- 当前 Integration `8100 /health` 可达；本次未重启唯一 Electron、未新增平台／Signer请求、
  未写 Integration 业务数据，也未触碰 Main 或生产数据库。
- PostgreSQL Session 场景继续由原 CI disposable PostgreSQL 执行；本机离线结果不冒充新的
  PG、平台、容器、原生客户端、安装包或生产验收。

