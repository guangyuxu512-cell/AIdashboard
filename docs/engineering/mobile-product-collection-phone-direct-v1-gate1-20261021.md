# 手机直传中控：最小差异与配对交接

## 1. 范围与准确状态

- 分支：`feat/mobile-product-collection-integration-v1`；本次直接父提交
  `ed890f556ef75a015ec496872f31794f3b158aa0`。本记录随本地候选提交，精确 SHA 见交付回执。
- 只处理当前“手机原包直接上传中控、NAS 仅任务分配和终态”的收窄任务；不恢复历史选品、登录、手机自动化等任务。
- 中控原 `POST /api/v1/mobile-collection/ingest/{attempt_id}`、Ingest Service、严格 V1/V2 parser、
  cleaner Adapter、版本/商品入库、状态 outbox 和 Dispatch↔NAS Job 关联全部复用。
- 中控最小差异隔离验证通过；整体 **PARTIAL / 外部配对 BLOCKED**。没有实机直传、NAS 生产接口或 Gate 2 成功证据。

## 2. 实际代码差异

仅 `backend/app/modules/product_collection/internal_api.py` 有运行代码变化：

- 原 attempt 注册与同批次 credential refresh 的响应加入 `Cache-Control: no-store`，避免手机交接所需
  短期凭据被缓存。DTO、路径、认证、HMAC 派生、TTL、幂等 ID、fence 和原包接收流程不变。
- 没有第二个原包入口，没有新状态系统、Schema、Migration、依赖或业务队列。
- 原 Task 创建 HTTP Adapter、`dispatch_id/external_job_id/gateway_job_id` 关系和状态-only Adapter 保留，
  不为适应 NAS legacy 响应而放宽身份校验，不把任意同商品活跃 Job 绑定给另一个 Dispatch。

契约同步在 `backend/docs/27-手机商品资料采集真实接入V1.md`，覆盖直传路径、独立描述的凭据交接、
成功/重复/失败回执、同包重传、删除本地待传包的前提及下述外部缺口；不再要求原包经 NAS 中转。

## 3. 手机项目最小交接契约

1. NAS 以服务身份调用中控已有 `/internal/mobile-collection/v1/attempts/register`，绑定当前
   Dispatch、Job、Device、Batch、平台商品和真实 lease；不是预造 Batch。
2. 原注册返回的 `controlIngest{protocol,attemptId,uploadUrl,credential,credentialId,expiresAt}`
   独立附到当前手机的受保护任务领取结果；不写入 Raw 正文，不向手机提供服务 Token/HMAC key。
3. 手机沿用原包生成逻辑，把原 UTF-8 JSON 直接 POST 到其中的中控 `uploadUrl`；Authorization 使用
   此短期 credential。原 `taskContext.jobId/captureBatchId/sourcePlatform/sourceProductId` 不改为
   人员 request_id，也不添加 Team。原平台详情、SKU、SHA 字段不删改。
4. 只有匹配 attempt/batch 的 `202 + ok=true + receipt.accepted=true + received/duplicate + receiptId`
   才证明中控 Raw 已可靠接收，可删除对应本地待传包；不等于商品已入库。
5. 超时、连接中断、无有效回执只有限重传同一包，不再次抓详情/SKU。凭据过期需要 NAS 以服务身份
   经原 internal refresh 续发同批次凭据；不重新 claim、不换 Batch。404/409/413/422 保留原包及错误。
6. 中控原 Processor 提交 Version/Product/Persist Receipt 后，outbox 只发送 Job/Batch/Receipt/终态等
   元数据给 NAS；失败如实发送失败，不发送 Raw、UU、SKU 或商品正文。

## 4. 外部接口证据与精确缺口

只读核对的是 NAS 源码快照 `e4f19b9bb3e6546947d7dcd26586892ccac62a69`，没有读取实时配置、调用 NAS，
也不能据此认定生产运行该版本。该快照不是本轮部署候选，不推进旧 relay/deployable 方案。

| 缺口 | 已核对事实 | 下一责任边界 |
|---|---|---|
| 凭据到手机 | `claimCollectionJob` 已取到注册结果，但响应只返回 `job/settings`，没有 `controlIngest`；内部 `refreshControlIngestCredential` 也不是手机已可调用的公开续发入口 | 规划/NAS Owner 确认最小受保护透传和同批次续传路径；中控注册/刷新响应已具备所需字段 |
| 仅状态完成 | 旧 `PATCH /api/v1/jobs/{jobId}` 允许 product completed 的条件是 captured/converted 且 `result_capture_id IS NOT NULL`，不能用于“原包不落 NAS”的完成回报 | 规划/NAS Owner 确认既有可用的 status-only 完成接口；不补造 NAS 结果、不上传原包绕过 |
| 隔离契约不等于部署 | 中控保留的 `/api/v1/control/collection-settlements` 仅发元数据，但来源是此前隔离配对实现；legacy 创建响应也不能自动当成中控严格派发契约 | 先冻结实际 NAS 接口配对，再由 ca97 安排受控集成；本 Owner 不修改 NAS 核心或部署旧候选 |

这不是 parser、cleaner 或商品入库缺失，不应再开发第二份实现。缺口也不能用真实手机向 NAS 继续传原包来掩盖。

## 5. 本候选实际验证

| 验证 | 实际命令/入口 | 结果 |
|---|---|---|
| Product Collection 非 PG 定向 | Node 24 执行 ignored `run_unit_isolated.mjs`，隔离 cwd/environment，无 `.env`/后台消费者 | **122 PASS**，含本次 2 项注册/刷新认证与 no-store 验证 |
| 真实 Feature PostgreSQL 原有+直传边界 | `backend/.venv/Scripts/python.exe -m pytest tests/integration/test_postgresql_collection_media_budget.py -o addopts= -q`（cwd backend） | **5 PASS**，其中本次直传流程 2 项；14.33s |
| strict 契约验证 | Node 24 + 已安装 pnpm：`pnpm verify --strict --report=.codex/mobile-phone-direct-20261021/verify-strict.json` | exit **0**；known/new/stale 全 0；10 Node、2 AST、9 Frontend contract 通过 |
| 编译与 whitespace | `python -m compileall -q`（本次 3 个 Python 路径）；`git diff --check` | PASS |

PG 两项使用真实中控 API、Ingest Service、Processing Service、Repository 与数据库；手机/NAS HTTP peer 及
cleaner 输出是合成替身。覆盖：注册→原入口原包接收→Raw/Hash 确认→入库成功或 cleaner 失败→相同原包
在终态重发仍返回原 receipt duplicate→异内容 409/错误 token 401→仅状态 outbox→人员查询真实终态。
合成回调精确断言请求仅含终态白名单，不含商品包。未使用人工改表伪造成功，未让 NAS 保存原包。

Feature PG 精确数据库 `control_center_feat_mobile_product_collection_integration`、角色
`control_center_dev_user`、Head `20261020_0049`；没有 upgrade/downgrade/check Migration。
所有新增夹具在未提交外层事务内使用 savepoint，测试结束整体 rollback，不会被外部消费者看见。
前后九表数量和 SHA-256 完全相同：Request2、Item2、Dispatch2、Attempt3，其他五表0；活动 Dispatch0、
pending Item0。三个实际自动开关始终 false，未启动消费者。

既有两份真实原包的离线 parser/既有 cleaner 证据复用：均 19 SKU / 8 主图 / 5 详情图；本轮没有重复
采集，也不把它们或旧的 120 定向测试写成手机直传实机通过。仅有既有 Starlette/httpx deprecation warning。

NOT_RUN：本轮全 Backend 套件、真实手机/NAS/Gateway/平台请求、Integration/生产数据库、Electron、
新窗口、APK、部署、push/PR、GitHub CI、dev/main 合并。无数据库迁移或第二套接收程序。

## 6. 交接与恢复

- 交付为本地可审查 Candidate 与本记录；不自行跨会话发送，由当前会话/规划转交 ca97。
- ca97 先独立复核中控候选和实际外部配对，再按另行授权安排一台设备一个任务的 direct 上传验证。
  必须观察手机原包直达中控、Receipt、Product/Version 和对应 NAS 终态；未满足前整体保持 PARTIAL。
- 本轮不动真实服务、端口、受保护凭据或开关；不允许把生产 relay 切换作为本候选隐含步骤。
- 若需回退，只回退本提交的响应头/测试/契约说明；保留原业务表、Raw、Version、Receipt 和审计，
  不降级清库、不回退整个 Feature，不删除手机待传包。
- 人类正在独立整理的 `AGENTS.md` 与 `docs/engineering/history/` 未纳入本次提交；不 stash/覆盖/清理。
