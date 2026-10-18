# ShopSession 采集就绪规则与关键 Verify Gate 1

## 结论与边界

- 分支 `feat/session-collection-readiness-v1` 建立于精确 Green
  `a445981f2c867f4d3fc01aaecf03960479209e87`；最终 Candidate 以正式 Handoff 的完整 SHA 为准。
- 本次只统一服务器采集前的 ShopSession 判定，让选品与经营真实消费同一规则，并补
  ShopSession / 选品品牌关键 Verify。没有 UI、Schema、Migration、依赖、经营调度、平台请求或生产变更。
- 商品数据 0047 未进入本分支。后续商品模块由 7d55 在本候选成为精确 Green 后正常 no-ff 同步，
  再调用本页列出的公共入口；不能复制判定表或把本分支冒充商品数据整体完成。

## 公共规则与消费点

`app.modules.sessions.collection_readiness` 提供两个公开入口：

1. `classify_collection_readiness(metadata, now, validation_freshness)` 是无解密、无数据库写入、无平台 I/O
   的纯决策；区分未配置、需要权威验证、可直接使用和需要重新登录。
2. `bind_collection_auth_context(health, context, expected_platform)` 将权威检查结果绑定到相同 Shop、平台和
   Session 版本，拒绝错店、错平台及检查后版本变化。

| 事实 | 结果 |
| --- | --- |
| 未配置 | 拒绝，不发身份或业务请求 |
| `captured` | 先做一次权威身份验证，成功后才能采集 |
| `valid` 且验证时间新鲜 | 复用缓存验证，进入该次业务请求 |
| `valid` 但验证缺失、陈旧、未来或早于采集 | 先做一次权威身份验证 |
| `invalid` / `refresh_required` | 拒绝并提示重新登录，不发身份或业务请求 |
| 健康检查后版本或身份改变 | 拒绝旧上下文，不能覆盖新 Session |

Cookie `expires_at` 只用于预警，不再被选品单独当作失效门禁。只有身份或业务 Connector 明确返回
`AUTH_INVALID` 才将当前版本标记 invalid；版本冲突保护较新的 Electron 刷新。网络、Signer、解析和一般
业务拒绝均保持原错误，不修改 Session。

选品的 `SelectionStoredSessionIO.session_context` 现在显式执行一次 HealthService，再取并绑定上下文；一个
Run 的分页和 `basic_info` 复用这份上下文，不增加逐页身份请求。业务请求若明确认证失效，仅 CAS 标记该旧
版本；其它失败不改状态。经营 collector 继续使用原 HealthService 和恢复状态机，只把健康结果与上下文通过
同一 binder 绑定，既有 Cookie 更新、失败分类和显式恢复边界不变。

## Verify 增量

- 登记后端 `ShopSessionStatus` 对 PC 原始 DTO、ViewModel 与 `SHOP_SESSION_STATUS_META` 的真实消费关系。
- 登记 `ShopSessionMetadataRead` 对原始 DTO 和显式 ViewModel 字段名映射。新增状态或字段未同步会失败。
- 离线运行探针使用独立固定期望核对当前品牌 `all=-1 / known=1 / unknown=0`，以及历史冻结 v7/v8
  `known=0 / unknown=1` Reader 的原值 round-trip。期望侧不引用实现常量。
- 负向子进程故意交换 known/unknown，真实退出 1；已有“服务端增加状态但消费方未同步”负向测试继续覆盖
  Enum 联动。`known-differences.json` 未修改，仍是精确 28 项。

## Gate 1 实际证据

| 检查 | 结果 |
| --- | --- |
| 新测试修前 | 因 `collection_readiness` 模块不存在在收集阶段失败，证明用例先于实现 |
| Session/选品/经营定向 pytest | 62 passed；含未配置、captured、陈旧/未来/乱序、新鲜但 Cookie 元数据过期、明确失效、错店、版本冲突、AUTH_INVALID 与非认证失败 |
| Backend 原完整离线 pytest | 899 passed、378 integration deselected；仅既有 Starlette/httpx deprecation warning |
| `python -m compileall`（全部改动 Python 运行文件） | exit 0 |
| Node 24.19 / pnpm 11.25：`pnpm verify` | exit 0；12 Enum、5 mapping、15 DTO、4 enum binding；28 known、0 new、0 stale |
| 同环境 `pnpm verify --strict` | 预期 exit 1；仅原 28 failures，0 stale |
| `pnpm verify --full --only=backend` | exit 0；899 passed、378 deselected；28 known、0 new、0 stale |
| MJS Prettier 与 `git diff --check` | exit 0 |

安全报告位于 ignored `.codex/`，无 Cookie、Token、签名、连接串或完整敏感 URL：

- `session-readiness-verify-default-final.json` SHA256
  `c265c9e7e3e9f03e6b6a2aae8ec0329dba13af9b3e0ad19cf54cedf40834ee12`。
- `session-readiness-verify-strict-final.json` SHA256
  `40767a654a12786cda8f0e05d25fc278e30dbea40fdd46c181c236a897ca84c3`。
- `session-readiness-verify-full-backend-final.json` SHA256
  `a0fe81c0455356adaa9c317b2411007d029e1448caee2ba322f5f68360141892`。
- `known-differences.json` SHA256 仍为
  `4ddacab88bc5a67737a024138ef9f487d6d536b48944092c46ab8ac79258c86b`，且无 diff。

一次 Backend 全量命令误从仓库根目录运行，因同时收集 Worker 的同名 `app` 包而产生 16 个收集错误；
它不是产品测试失败。随后从项目规定的 `backend/` 目录原样执行得到上表 899 PASS。一次 Prettier 命令误把
Python 和旧中文 Markdown 交给不支持的解析器而 exit 2；随后仅检查适用的 MJS 并通过，没有批量重排旧文档。

## 未执行、回退与下一负责人

- 未连接本地、Integration 或生产 PostgreSQL；未执行 Migration、真实平台、Signer Runtime、原生 Electron、
  容器、部署或生产 smoke。两份会绑定端口的 Backend 测试仍按 Verify 既有 profile 明确 NOT_RUN。
- 回退只需正常回退本候选代码与 Verify 登记；没有数据或配置恢复动作。若新 Session 已在执行中，仍由既有
  版本 CAS、租约和消费者失败处理收尾。
- ca97：独立 Gate 2 复核公共矩阵、真实消费点、默认/strict/负向 Verify 与完整 Backend profile，再形成精确
  Green。本候选不是生产发布授权。
- 7d55：收到 ca97 的精确共享 Green 后 no-ff 同步，在商品模块短事务读取授权事实，事务外调用
  `ShopSessionHealthService.check(force=False)`，再 Accessor + `bind_collection_auth_context`；随后追加商品专属
  17 指标/DTO/状态 Verify。不得再按 `VALID + validated_at` 复制一套局部规则。
