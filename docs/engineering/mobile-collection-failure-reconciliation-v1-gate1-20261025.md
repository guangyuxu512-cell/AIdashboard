# 手机商品采集网关失败状态同步

## 基线与范围

Owner 为 81a1，下一责任人为 ca97。分支 `hotfix/mobile-collection-failure-reconciliation-v1` 从精确
Green `980a215c2c9f92f2b780529b2cea1eb75545ec22` 创建；已独立核对
[CI 40150589086](https://github.com/guangyuxu512-cell/AIdashboard/actions/runs/40150589086) success。
精确新 Candidate 和远端核验见正式 Handoff。原分支/候选及用户 `AGENTS.md`、工程历史目录保留。

ca97 只读证据对应 Request `31a29c92-3e05-44e9-9942-82d3082f6ce0`、NAS Job
`7990e8d5-858c-4071-83d2-1cc3b64b4cda`：NAS failed 3/3，中控 Request/Item/Dispatch/当前 Attempt
仍 running，无 Upload；前两 Attempt 已 superseded。旧实现只在取消时对账，没有独立的失败状态查询。
本 Owner 未读取或修改生产任务；该证据用于修复与后续正式验收，不作为本轮新实测。

本轮只补状态同步。手机 SKU 排查暂停，不改采集逻辑、APK、配对、商品库功能、前端、依赖、配置或 Schema。

## 实现与边界

五个运行文件均在 `backend/app/modules/product_collection/`：

- `ports.py`：增加窄只读 `Gateway.status`、安全状态投影及冻结的本次查询身份；不增加任务状态系统。
- `gateway.py`：复用原 HTTP 与 control token，严格解析 NAS 的 root 状态 DTO；Job 与 external ID
  都须匹配，查询参数独立 URL 编码。任意 result、未知字段/状态、错误类型或无时区时间均拒绝，不使用管理员凭据。
- `repository.py`：原表和索引上短事务领取一个到期的当前 dispatched/running Job。复用
  `next_attempt_at` 限频，不增加 delivery/capture 次数；已接收或处理中上传不进入该查询。
- `dispatch_service.py`：提交查询身份后才做 HTTP，回写时重新锁定并校验 Team、gateway/Job/external、
  当前 Dispatch、当前 Attempt/批次/设备。只接受 authoritative failed；沿原终态 helper 原子更新
  Dispatch=`execution_failed`、Item/当前 Attempt=`failed`，Request 走原聚合。重复终态、旧批次/旧派发、
  接收期间的上传及任何身份不匹配都不覆盖现有事实。
- `executor.py`：在原派发循环的取消检查之后、计划/投递之前有界执行一次状态检查，不增加消费者/队列。
  网络或无效响应只保留业务状态并等待下一次到期检查，正常派发仍能继续；不自动 retry/recapture。

错误继续使用固定中控码 `PRODUCT_COLLECTION_GATEWAY_EXECUTION_FAILED` 和阶段 `gateway_execution`。
已取证的完整超时原文精确映射为“手机采集等待本批次完整包超时（尝试 3/3 次）”；短超时原文也有独立
白名单。其余 lastError 仅显示通用失败及有效次数，不透传任意诊断、URL 或凭据，也不把 LSPosed/插件建议
当作已证实根因。现有人员任务详情 API 已可读取安全错误；无需新增前端字段。

同一 Job 的 pending/running/retry_wait/captured/completed/canceled 均不据此改业务状态。没有本地
当前 Attempt 时，只接受同样无批次的绑定，不猜测最后批次。已有失败/取消历史、次数预算和人工恢复入口保留；
3/3 后普通 retry 仍拒绝，显式 recapture 才创建新 Dispatch。没有伪造 Receipt、商品或版本。

## NAS 配对依赖

NAS 分支 `codex/control-job-status-query-v1` 精确 Candidate
`65f66d81bafcc4d827f9a1db42130b62ad691ada`，parent
`2d3466876d95a859114aaa4ffeda519a4d913dd3`。

冻结请求为 `GET /api/v1/jobs/{gatewayJobId}/result?externalJobId={URL编码后的externalJobId}`，
Bearer 使用原 CONTROL_DISPATCH_TOKEN。严格 root 包含 12 个字段：ok、jobId、externalJobId、status、
sourcePlatform、sourceProductId、captureBatchId、attempts、maxAttempts、lastError、updatedAt、finishedAt。
不是旧管理员 result 包络，不返回完整 result 或 Token。NAS 对未知/非 central/身份不匹配返回 404，错误凭据 401。

本轮只读提取该精确提交的 `controlCollectionJobStatus` 和 `isoTimestamp`，用内存 SELECT 替身生成真实
源码投影，再交中控严格 adapter 解析；键、类型、19 位 ID、安全原因和编码契约匹配。该验证不连接 NAS 或
其数据库，不是实际 NAS HTTP 联调。NAS Owner 提供的 28/28 属于其候选证据，本轮未将它写成中控重跑。
ca97 另已确认生产终态保留的批次与中控 Attempt3 一致；本 Owner 没有重复查询生产。

## 本轮实际验证

| 验证 | 结果 |
|---|---|
| 隔离 Feature PostgreSQL 定向及原取消/重采回归 | 32 PASS，68.523s，2 个原真实包用例按范围 deselect；其中本次 20 项，原适用回归 12 项 |
| 三次失败与 API | Request/Item/Dispatch/当前 Attempt 收敛，前两 Attempt 保持 superseded；安全错误可通过原 API 读取，Upload 数保持 0 |
| 保护与恢复 | 重复同步不改完成时间；旧派发/批次、Team/设备/Attempt 身份错误不影响新任务；查询期间收到 202 后不被失败覆盖；普通预算不重置，显式重采可用 |
| 故障与非终态 | 七种非 failed/未知状态和网络错误均保留业务状态；HTTP 在 Session 事务外，重复到期检查限频 |
| 完整 Backend 离线及 strict Verify | `pnpm verify --strict --full --only=backend --report=.codex/mobile-collection-failure-sync-20261025/verify-strict-backend.json`：exit 0，114.23s；Backend 1252 PASS/510 deselected，pytest 87.50s；known/new/stale 全 0，10 Node/2 AST/9 Frontend 契约通过 |
| NAS 源投影合成配对 | 精确 65f66d 的只读投影生成 12 字段，实际中控 adapter 接受；外部 ID 特殊字符编码另有单元回归 |
| 编译/whitespace/范围 | compileall、git diff --check 通过；Frontend/Electron/Worker/Mobile/配置/依赖/迁移均无差异 |

PG 命令在 backend 目录执行：

```text
.venv/Scripts/python.exe -m pytest tests/integration/test_postgresql_collection_status.py tests/integration/test_postgresql_collection_recapture_cancel.py tests/integration/test_postgresql_collection_media_budget.py -k 'not real_package_via' -o addopts= -q --tb=short --junitxml=../.codex/mobile-collection-failure-sync-20261025/pg-final.xml
```

首轮新增 PG 15 项通过。补上传竞态后的一次扩展运行 27 PASS/1 FAIL，失败仅为测试误读不存在的
`received_count` 字段；已按现有 DTO 改为 running_count/Item received，未改公开接口。最终 32 项通过。
只有既有 Starlette/httpx 弃用 warning。Node 24.22.1、现有 pnpm 11.25.0，项目 pin/依赖不变。

## 数据与交付状态

ca97 已批准原 Feature DB `control_center_feat_mobile_product_collection_integration`，角色
`control_center_dev_user`、127.0.0.1:35433、单一 Head `20261020_0049`。三实际开关 false；测试应用无
lifespan，活动夹具仅在外层事务/savepoint 内可见，结束整体 rollback。九表数量/整表摘要前后一致：
原 2 Request/2 Item/2 Dispatch/3 Attempt 保留，活动 Dispatch/Pending Item 都为 0。无升级、降级或清库。

ignored 证据为 `.codex/mobile-collection-failure-sync-20261025/` 的 pg-final.xml、strict 报告及 NAS
合成投影；前后只读摘要在 `.codex/mobile-media-budget-20261021/pg-status-{before,after}.json`。
修改两份原 PG Gateway 替身仅为补齐只读 port，不削弱原预算、取消或去重断言。

本候选尚未 Gate 2、合入 dev/main 或部署，未对真实 NAS/手机/平台发请求，也未启用开关或新增任务。
ca97 须组合两端精确候选做独立验收，再交 Main 正式发布；生产旧任务只由发布后的正式同步路径收尾，
不得手工改表或借本修复自动重试/重采。原前端与实机验收不重复扩大。

回滚正常 revert 本次新增同步及测试/契约，保留已正确收敛的状态和全部历史，不把失败改回 running。
NAS 只读端口向后兼容，是否回滚由其 Owner 单独处理；中控不修改对端代码或配置。
