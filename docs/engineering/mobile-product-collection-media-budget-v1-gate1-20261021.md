# 手机完整包接收与隔离单次预算返修 Gate 1

## 范围和版本

- Owner：81a1；分支 `feat/mobile-product-collection-integration-v1`。
- 直接父提交：`efc554584157caaf28d662c70cf5894a6e4ae7af`；最终本地 Candidate 以本轮提交回报完整 SHA 为准。
- 仅修中控两项：Collector V2 合法媒体 URL 的误拒；新 Dispatch 的可配置、可稳定重放手机采集预算。
- 保留 V2/三个 SHA 格式、重复回传/丢回执、取消终态及迟到 fence。无 Schema/Migration；0049 原字节不改。
- 外部网关只读核对：`e4f19b9bb3e6546947d7dcd26586892ccac62a69`。前端、网关、手机和 APK 均未修改或启动。

## 真实失败与离线修复

ca97 的既有实机已经成功采到同一商品原包，中央接收时为 422
`PRODUCT_COLLECTION_PAYLOAD_INVALID`，没有 Upload Receipt/Product/Version。原任务已正式取消，手机已恢复；
本轮不重采、不改这些旧失败记录。

对授权的同一个 Git 外原包做正式 parser → `ExistingUuProductPackageCleaner` 离线验证：

- 原始文件 829681 bytes，SHA-256
  `22f3a102553770672a3cf39aa6c32b8e1a11c585d47ae2f8738fb6372782f301`，验证前后相同。
- 修前正式 parser 在 `detailBody` 拒绝 credential-bearing URL。取证共 31 个 HTTPS 媒体 URL，资源级
  `sign/x-signature` 被通用认证 query 判断误拒；没有输出原 URL、query 值或原响应正文。
- 修后正式 parser 接受 V2，所有原提交字段逐值保留；既有默认值规范化仍按原模型执行。
  该包原 taskContext 未显式写入默认 `recaptureRequested=false`，原模型规范化会补此默认值。
  文件 SHA 与模型规范化 content hash 不混为一个值。本轮没有重写原包或改变原规范化策略。
- 规范化 content SHA-256 为
  `3784c23e85ea3287aace6c3cb1657a74f2bf3e50715243a2ed517ef1bc85c3c5`。
- 同一正式 cleaner 输出 **19 SKU / 8 主图 / 5 详情图**，商品长 ID 与原 taskContext 一致。
- Raw/不可变 UU 保留资源来源；`primary_image_url` 展示投影仍走原 allowlist/HTTPS/userinfo/query 净化。
  此次只为离线验证使用从原包观察到的 host 集合，未改运行配置或扩大生产 host allowlist。
- 无数据库写入、外部媒体请求或手机操作。安全计数/哈希证据在本树 ignored
  `.codex/mobile-media-budget-20261021/real-package-proof.json`；原包保留 Git 外，不复制为测试夹具。

修复只在 V2 `detailBody` 的已证实媒体结构中识别资源签名，完整映射见后端契约第 6 节。
实际 JSON 数组与对象路径、精确 host、HTTPS、资源路径和 query-name 集合共同生效。V1/skuBody、任意
字段、伪造点路径或对象星号、其他 API path/域名、Cookie/Authorization/headers、真实认证 Token、
`a_bogus/signature`、userinfo、非法端口和未知 query 均不继承例外。未删除字段、未全域开放签名 URL。

## 手机采集预算

新增受保护部署配置 `BACKEND_PRODUCT_COLLECTION_CAPTURE_MAX_ATTEMPTS`，默认 3、合法整数 1–3。
隔离 Gate 设置 1；前端请求格式和页面不变。消费者计划初次派发、显式 recapture 都传入同一个配置值。
`maxAttempts` 与既有 canonical payload 中的 `max_attempts` 使用同一数值。

为保持已应用 0049 和旧数据不变，重放通过已保存 canonical hash 恢复有限的六个合法
`recapture × budget` 组合；同时验证原 external job ID。匹配失败时在领取提交前拒绝，禁止重新按当前
配置拼出不同内容。原默认 3 的 payload/hash 保持字节语义兼容；初次显式重采标志也由 hash 确认，不猜次数。

- 中央 delivery 网络重试与手机 capture 预算相互独立：模拟网关已接受但响应丢失，中央仍能安全投递同一
  key/hash/body；配置由 1 改为 3 后，原命令仍发送 `maxAttempts=1`。
- 原预算 1 的 Job 达到一次后，普通 retry 返回 409，不能靠配置变化扩大；累计次数/原失败保留。
- 正常预算 3 的执行失败仍允许原 Job 有限 retry，不清累计次数；耗尽后拒绝。
- 显式 recapture 仍新建 Dispatch/key 并按当时配置冻结新预算，旧 Dispatch/失败/次数不变。

只读核对 e4f 网关正式 central-ingest handler：读取请求 `maxAttempts`，并作为 INSERT 的
`collection_jobs.max_attempts` 参数保存。中控本轮真实 PG + 合成 HTTP 已证明发送链路，不冒称网关现场已
保存/设备已领取。下一责任人须在设备 claim 关闭时核对实际 Job 的预算 1，确认后才进入原受控实机流程。

## 实际修改文件

| 文件 | 用途 |
|---|---|
| `backend/app/modules/product_collection/media_urls.py` | V2 已证实媒体策略；复用原 URL 安全解析 |
| `backend/app/modules/product_collection/contracts.py`、`payload.py` | 入口媒体上下文与原显示 URL 净化分离；其他边界保留 |
| `backend/app/core/config/settings.py`、`backend/.env.example` | 有界 capture 预算配置，默认 3 |
| `backend/app/modules/product_collection/dispatch_service.py`、`ports.py` | 新命令冻结预算；原 hash 重建同一 wire payload；漂移 fail-closed |
| `backend/app/modules/product_collection/executor.py`、`api.py`、`human_service.py` | 消费者/显式重采传递配置，有限 retry 同时检查冻结额度 |
| `backend/tests/test_product_collection_media_urls.py` | 合法资源与认证/域名/路径/协议/结构负向回归 |
| `backend/tests/test_product_collection_capture_budget.py` | 默认/配置预算、旧 hash、重放与内容漂移 |
| `backend/tests/integration/test_postgresql_collection_media_budget.py` | 正式 API/真实 PG/合成 HTTP 的预算、重放、有限 retry/重采及 V2 回执 |
| `backend/docs/27-手机商品资料采集真实接入V1.md`、本文件 | 契约、配置和 Gate 1 交接 |

独立的人类规则清理 `AGENTS.md` 修改及 `docs/engineering/history/` 归档原样保留，**不暂存、不提交**。
AGENTS 文件没有追加任务进度。临时脚本/安全证据只写 ignored `.codex`，不含原 URL/query 值。

## 验证记录

| 检查 | 实际结果 |
|---|---|
| 修前媒体回归 | 15 failed / 24 passed：14 个合法资源用例被误拒，媒体字段的 FTP 负向用例暴露原缺口 |
| 修前预算回归 | 16 failed：无配置传递/重建/预算校验能力 |
| 最终 Product Collection 非 PG | 104 passed；命令见下；只保留既有 Starlette/httpx deprecation warning |
| 最终 Feature PG 定向 | 6 passed；3 个新增定向场景加原有限 retry/recapture、最终 delivery lease 恢复、终态同内容重放 |
| Backend 默认完整离线 | 最终冻结源码 1189 passed / 479 integration deselected，94.76s；仅既有 warning |
| 正式 parser → 原 cleaner | 原包 hash/身份保留，19/8/5；没有媒体请求或业务写入 |
| compileall / diff | Product Collection/Settings/三个新测试 compileall exit0；`git diff --check` exit0 |
| Node24 strict Verify | `pnpm verify --strict --report=.codex/mobile-media-budget-20261021/verify-strict.json` exit0；0 known/new/stale；10 Node/2 AST 负测、ASGI 及9个客户端探针通过 |

首次直接 `node scripts/verify.mjs --strict` 返回 exit2：该入口要求由 pnpm 提供 `npm_execpath`，
直接 Node 调用缺少 runner，属于验证命令准备问题；未改 checker/例外/工程代码。随后使用既有
Node24.19 / pnpm11.25 正式 `pnpm verify --strict` 通过，未安装新包或改依赖/lock。

实际命令（在 `backend`，解释器为现有 `.venv/Scripts/python.exe`）：

```text
python -m pytest -m "not integration" -o addopts="" -q
$collectionTests = @(rg --files tests -g 'test_product_collection_*.py' | Where-Object { $_ -notmatch 'integration' })
python -m pytest -m "not integration" -o addopts="" -q @collectionTests
python -m pytest -m integration -o addopts="" -q tests/integration/test_postgresql_collection_media_budget.py tests/integration/test_postgresql_product_collection.py::test_finite_retry_reuses_dispatch_and_recapture_creates_new_identity tests/integration/test_postgresql_product_collection.py::test_expired_final_delivery_claim_is_closed_after_restart tests/integration/test_postgresql_product_collection.py::test_terminal_upload_replay_is_stable_and_still_authenticates
```

PG 仅用已登记 `control_center_feat_mobile_product_collection_integration` / `control_center_dev_user`，精确
Head0049。先确认消费者三开关 false、8101 无监听、无其他 active client、旧活动 Dispatch/pending Item 均 0。
新增用例的 Service commit 仅释放 savepoint，外层事务未提交，其他进程看不到夹具；最终外层 rollback。
原三条定向回归只产生自己的稳定 fixture，清理按其精确 ID。前后九表行数/整行安全摘要均核对保持，旧
2 Request/2 Item/2 Dispatch/3 Attempt 及原失败记录不变；Receipt/Product/Version 仍 0。

## 未验证与下一责任人

- Gate 1 为中控代码、现有真实原包离线、合成 HTTP 和独立 Feature PG 证据。
- 未启动或操作手机/ADB/APK/Gateway/NAS/生产，未发真实任务，未改配置/旧失败记录，没有新 UI/数据库结构。
- 实际前端 → 真实 Gateway 持久 `maxAttempts=1` 的 claim 前核验、同一完整包接收/入库/商品版本/结算及唯一
  Electron 展示由规划交 ca97 独立 Gate 2；本候选尚不能标为实机闭环通过。
- 本地提交、未 push；没有 PR/CI、dev/main 合并或发布。本轮在本聊天交规划读取，不跨聊天下发任务。
- 回滚保留0049/历史/Raw/Version/Receipt，关闭三个既有消费者；若存在新预算 1/2 Dispatch，必须保留本次
  预算 reader，不回退为把所有重放都发送 3 的旧实现。
