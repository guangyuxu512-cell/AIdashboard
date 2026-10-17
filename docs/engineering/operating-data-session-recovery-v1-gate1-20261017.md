# 经营采集会话恢复 Gate 1

本次将已有单项 Session 恢复能力接入经营看板，并允许用户明确选择在原执行器内复核仍有效但验证已过期的会话。Owner 为 81a1，交 ca97 独立 Gate 2；不修改登录捕获、原每日计划或普通补缺规则。

## 基线与资源

- 分支 `feat/operating-data-session-recovery-v1`，直接起点为已独立核验的 Green `bef7093b755cea60fda55bbcc6177b5723d4738a`，CI 38993305361 成功。最终 Candidate 以本记录所在提交及正式 Handoff 的完整 SHA 为准。
- 既有选品 A/B 已发布，本轮不切回旧候选或重做选品。旧登录、清理及各 Feature 分支、安装包和本机证据保留。
- ca97/Main 已核准复用 `control_center_feat_product_selection`、最小角色 `control_center_dev_user` 及现有受保护的 35433 通道。真实 Head 为单一 `20261015_0046`，无 DDL、Migration 或新 Slot；不借用 7d55 的商品 0047。
- 四个经营/选品自动及执行开关在 ignored 本地配置中显式为 false，并由测试读取实际 Settings 断言。只向受控 Service/Executor 注入测试设置；不启用后台循环或修改 Integration/生产。
- Feature 库原 users/teams/shops 的计数及逐行哈希在每项测试前后保持一致。仅新增带 `stage-2a1` 标识的合成人员、店铺、会话和执行事实，按当次稳定 UUID 清理，不全库清理、不降级重建。

## 诊断依据与恢复边界

Main 已提供生产只读记录：8 项原 DAILY 失败均为 `session_preparation / SHOP_SESSION_VALIDATION_FAILED`、retryable、原尝试数和累计数均为 3；冷却已过，无成功事实或活动项。两店当前会话 VALID 且捕获晚于失败，但验证时间约 34 分钟前，不能把 VALID 当作仍在 300 秒新鲜期。该事实只解释本次资格阻塞，不证明历史平台失败的唯一原因。

本轮不对这 8 项真实生产记录执行恢复。测试使用相同故障形态的独立合成样本，不将模拟结果写成生产已补齐。

## 改动范围

1. `operating_dashboard` 原 Repository 批量读取会话版本、状态、时间及身份是否存在，不读取加密载荷。Service 对已有最多 20 个授权缺失样本附带安全恢复资格或阻止原因；读写共用同一政策，读取不验证、不排队。
2. 既有 retry Body 新增严格布尔 `revalidate_current_session=false`。显式 true 仍需单个原 Item 和精确版本，仅适用原 DAILY/FAILED/retryable 的上述会话准备失败。其它业务、签名、解析错误和非 DAILY 不扩围。
3. 原 `session-restored:{original_item_id}` 数据库去重保留，跨进程/版本仅一项恢复；旧失败及累计次数不改。显式选择只将 freshness 复核移入现有 collector，HTTP 无平台 I/O。原默认请求仍守 300/301 秒边界；202 不代表成功。
4. 原 HealthService 仍先权威复核，再读经营指标。仅原经营 factory 自己创建的独占 Session 选择 `before_platform_io` 回调，在身份及经营 I/O 前结束自身只读事务。默认回调为 None，不提交或回滚 API、登录或任意调用方事务；已 flush 写入也不靠 dirty 集合判为安全。Cookie 更新、版本 CAS 和原异常分类不变。
5. 经营看板原“查看缺失”复用 Naive Popover、AppButton、typed API 和现有 Job Query。明确单项恢复、等待复核、真实终态及重新读库；已接受的 pending 回执先写入既有查询缓存，防首次 GET 等待期重复点击。人员/团队/离页代次阻止旧结果覆盖当前界面。
6. 相关后端/前端契约及定向测试同步。无新 API 路径、状态系统、队列、基础组件、全局主题、Electron 或安装包改动；09:00、日期资格、退款时间口径、授权和停用检查沿用原实现。

## 验证结果

| 验证 | 结果与证据边界 |
| --- | --- |
| 后端相关 10 文件 | 129 PASS，6.15 秒；覆盖 Accessor、Session Service/refresh/诊断/Health、经营解析/collector/Service/API/scheduler。默认无 PostgreSQL/平台网络 |
| 独立 Feature PostgreSQL | 最终 8 PASS，50.37 秒；正式 ASGI/API、真实 ActorContextService/Repository、领取与回写、生产 collector factory/Health/Accessor/固定解析器；只有人员凭据和外部身份/指标适配器为合成 |
| 8 项恢复与完整更新 | 并发提交返回同一 Job，两执行器只领取一次；逐项完成后覆盖 4/12→12/12，0 金额/0 订单/退款每项 3 正常保存；共 2 次合成身份和 8 次合成经营调用。8 个旧失败仍 failed/attempt_count=3。完整更新连续两次无新 Job/Item、无额外外部调用 |
| 安全及故障 | 外团队不可访问，入队后撤权零外部调用；复核失败单次终态且保护旧成功值；300 秒允许/301 秒默认拒绝；默认 Health 不结束调用方已 flush 事务；租约超时后迟到结果拒绝；Cookie 更新 CAS 不覆盖并发新版本；版本变化、未来时间或停用均拒绝 |
| 经营前端 | 7 文件 38 PASS，7.64 秒；实际 QueryClient/VueQueryPlugin，pending 首次 GET、重复点击、拒绝、过期目标、团队变化及卸载迟到保护，不调用 Mock |
| 完全拦截的 Real Renderer | 4 PASS，22.5 秒；前三主题 1440×900、午夜青 1024×900。逐个原 Item 的请求、202 回执、Job 终态和后续读库响应严格对应上述 Feature API steps。API/外部请求全拦截，非现场连库或原生 Electron，不冒称平台实测 |
| 静态与构建 | lint、typecheck、实际 `pnpm build`（内部 Real/production）通过，构建 17.55 秒；保留既有大 chunk 警告。一次误调用不存在的 `build:real` 未执行构建，已改用正式脚本验证，不隐藏命令失误 |

首轮 PostgreSQL 揭示原只读事务仍覆盖身份 I/O，保持失败记录并通过限定 factory 所有权的回调修复；未修改测试的“外部 I/O 无事务”标准。首次页面验证还发现 202 后首次 GET 等待期间忙态空档，已通过现有 Query Cache 初始化修复。早期单主题 UI 记录与最终逐 Item 关联证据分开保留，不用于本轮闭环声明。

## 复现与本机证据

Backend 在已批准连接及四开关 false 下运行：

```powershell
# cwd: backend
.\.venv\Scripts\python.exe -m pytest tests/test_shop_session_auth_context.py tests/test_session_service.py tests/test_shop_session_refresh_service.py tests/test_shop_session_refresh_diagnostics.py tests/test_shop_session_health_service.py tests/test_douyin_operating_data.py tests/test_douyin_operating_data_executor.py tests/test_operating_dashboard_service.py tests/test_operating_dashboard_api.py tests/test_operating_dashboard_scheduler.py
.\.venv\Scripts\python.exe -m pytest -m integration tests/integration/test_postgresql_operating_session_recovery.py
```

专用 PG fixture 在连接前严格校验精确 Feature 库/角色/host/port，连接后复核 current_database/current_user/Head0046；不允许改成库名前缀以借用 Integration。所有执行器均限定 `collection_job_id`。Integration 仍有历史 2020 活动夹具，ca97 必须继续独立 pin 稳定 UUID，不清除或消费这些记录。

Frontend 实际命令：`pnpm exec vitest run src/features/operating-dashboard`、`pnpm lint`、`pnpm typecheck`、`pnpm build`。浏览器仅启用 4176 strictPort 的 Real Renderer，使用现有 Playwright，不启动 Backend 或新 Electron：

```powershell
# cwd: frontend；proof 由上面的专用 PG 用例生成，只有合成账号与安全业务字段
$env:PLAYWRIGHT_API_MODE='real'
$env:PLAYWRIGHT_OPERATING_RECOVERY_PROOF='C:\Users\Administrator\.codex\worktrees\81a1\中控台\.codex\operating-session-recovery-v1-20261017\feature-api-proof.json'
pnpm exec playwright test --config ../.codex/operating-session-recovery-v1-20261017/playwright.config.cts --output ../.codex/operating-session-recovery-v1-20261017/browser-final
```

新 Real E2E 已登记现有测试入口；未显式提供 proof 时跳过，不偷偷连接数据库或回退 Mock。临时 config、JSON、截图和本地配置均 ignored，不提交凭据或原始平台响应。

相对工作树根目录 `.codex/operating-session-recovery-v1-20261017/`：

- `feature-api-proof.json` SHA256 `bd6045662b067e806a5c6046a9f9aed6f5f5c440c74c4418b14189c2e2827661`。
- `validation-failure-api-proof.json` SHA256 `b2b60fe422b5caa01b5e571ddca978986cfc1461bcf4085b95fd337c931ac185`。
- `playwright.config.cts` SHA256 `b602efb9795efadc4a9cba0343e1fedb678fbb4b32e8f26a7cd73808d011bb77`。
- 最终八张截图在 `browser-final/operating-dashboard-recove-*/{theme}-recovery-{eligibility,complete}.png`。Owner 已查看四主题恢复入口及窄视口完成状态，弹层可滚动且不超出视口；不改原页面布局。

## 交接与恢复方案

ca97 接收精确 Candidate 后独立源审、Integration0046 数据保护及正式 API/实际加载版本验证；浏览器截图不能替代它的集成或原生证据。生产当前 8 项仍未恢复，平台与生产写入预算为 0；如需生产恢复须另行取得精确范围授权，不能按本记录自行执行。用户无需重复手动登录或做机械窗口 QA。

应用回退走正常版本回退，不降级数据库、不删除旧失败或恢复 Job、不重置次数/去重键。已排队任务按旧执行器兼容规则收尾，回滚 UI 不声称撤销已发请求。此轮不合 dev/main、不发布、不修改生产开关，也不把 Gate 1 写成生产已修复。
