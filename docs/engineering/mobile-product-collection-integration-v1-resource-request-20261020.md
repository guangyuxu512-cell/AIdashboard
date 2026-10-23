# 手机商品资料采集真实接入 V1：资源与 Schema 申请

## 1. 精确基线

- Feature Owner：81a1
- 分支：`feat/mobile-product-collection-integration-v1`
- 精确 Green / 当前 HEAD：`65ecf3f72a6ae9ea3114d7404841ad9aae876565`
- Integration 只读 Head：`20261019_0048`
- Migration：ca97 已分配唯一 active `20261020_0049`，计划文件
  `20261020_0049_mobile_product_collection_integration_v1.py`，down=`20261019_0048`；Schema 修订已
  `ACCEPT`，Feature DB 已完成 upgrade、downgrade、upgrade，当前精确 Head 为 0049。
- 外部手机仓库：只读核对，工作树原有改动保持；未修改 APK、NAS、手机或数据库。

完整业务/状态/Schema 契约见 `backend/docs/27-手机商品资料采集真实接入V1.md`。

## 2. 资源申请

| 资源 | 建议值 | 原因与限制 |
|---|---|---|
| Feature DB | `control_center_feat_mobile_product_collection_integration` | 独立、可重建；不得复用选品、商品数据、Integration、Main 或生产库 |
| 应用角色 | 既有最小角色 `control_center_dev_user` | 不申请 CREATEDB/CREATEROLE/SUPERUSER；仅由 ca97/DBAdmin 建库并授权 |
| 受保护连接 | ca97 已通过既有本机受保护机制交付 | 连接串不入 Git、文档或日志；使用前仍必须断言数据库名、角色与单一 Head |
| Backend | `127.0.0.1:8101` | 当前只读核对无监听；不得占 8100/5180、8103/4178 或启动第二 Electron |
| Frontend | 本阶段不申请 | 冻结 UI `e52570f…` 非 Green，后续仅经 ca97 批准正常 no-ff 消费并使用 Owner 端口 |
| Gateway Mock | 不申请独立端口 | 首轮用 HTTPX MockTransport/ASGI in-process；真实隔离联调再由 ca97 与外部 Owner 登记唯一地址 |

## 3. 申请的九表与最小理由

1. `product_library_groups`：Team 分组或未分组引用；
2. `product_library_products`：Team 级正式商品身份、当前投影与 adopted version/manual revision fence；
3. `product_library_product_versions`：不可变 UU/source 版本；
4. `product_collection_requests`：人员提交、幂等、取消和聚合状态；
5. `product_collection_items`：每个去重目标、候选来源、状态和当前派发；
6. `product_collection_dispatches`：到既有网关的可靠投递关系，不提供手机 claim；
7. `product_collection_capture_attempts`：网关 Job/Device/Capture Batch fence 与 ingest token hash；
8. `product_collection_upload_receipts`：Raw durable receive（202）与 Inbox lease；
9. `product_collection_persist_receipts`：清洗/数据库提交证明；统一网关结算 outbox 位于每个已接收包均有的
   `product_collection_upload_receipts`，避免清洗失败因不存在 Persist Receipt 而丢失结算重试。

另只对既有 `product_selection_candidates` 追加 `(candidate_id,team_id)` 唯一键，供 Item 建立同 Team
复合 RESTRICT FK；不改现有候选内容、业务唯一键或状态。

0047/0048 是 Shop 级指标快照及其采集队列，无法表达 Team 商品库、完整包版本、Device/Job/Batch、
双回执或人工编辑 fence；不改写、不借用。Product Selection Candidate 只作 RESTRICT 来源引用和
Service 可见性校验，不提升为商品库。

## 4. 审核要点逐项映射

- 业务 API 与 Team/candidate 可见性：契约第 4 节；
- 服务认证、设备身份和无明文凭据：第 3 节；
- 稳定键、唯一/FK/RESTRICT：第 3、7 节；
- 接收/入库双回执、幂等、迟到 fence、lease/heartbeat/restart：第 5、7、8 节；
- 完整包→既有 UU cleaner→商品库事务：第 5.4、6、8 节；
- cancel/retry/网关结算：第 4.2、5.4 节；
- PDD 人工、Douyin 自动、Taobao 关闭：第 1、5 节；
- upgrade/兼容/回滚/0047-48 保护：第 9、10 节；
- 精确表/字段/索引/约束：第 7 节。

## 5. 外部网关已确认事实

- 现有 claim 会原子增加 attempt、生成 `captureBatchId` 并绑定 Device；手机更新已有
  `jobId + deviceId + captureBatchId + allowed state` CAS。
- 202 durable receipt 只代表 received；现有清洗成功后任务才 completed；旧 batch 为 superseded。
- 当前 claim 未过滤平台/能力，heartbeat 不含 batch 且不续 Job，是接入前必须由外部 Owner 修复的 P0。
- 动态 `controlIngest` 需网关 claim 提交后向中控注册 attempt，失败 CAS 回 retry_wait/failed；
  旧客户端忽略新增字段。
- Android 当前只支持配对 base URL + Device Token；新增动态 URL/token 必须由外部 Owner 做成对最小改动。
  现有 `device_credentials.xml` 为 Hook 读取而放宽权限，不能承载新 secret；新 credential 必须由 signature
  Provider 写入 collector APK 独立 MODE_PRIVATE 存储，并由 collector 自身上传服务使用。
- 网络/网关有限 retry 复用原 Job/external key；只有人员 recapture 才新建 key。
- `controlIngest` 固定包含 protocol/attemptId/uploadUrl/credential/credentialId/expiresAt；同 batch 过期时
  仅在仍归属同 device 且未结算时续发，不重新 claim。

## 6. 已执行顺序与剩余边界

1. ca97 已登记唯一 Slot、Feature DB、受保护连接与 Backend 8101；
2. 双回执 Schema 已复审 ACCEPT，0049 文件及 Model 已按批准结构固化；
3. 0049 已在 Feature DB 完成 upgrade、空库 downgrade、再次 upgrade；
4. 中控 Model/Repository/Service/Human API/Internal API、HTTP Gateway Adapter、UU cleaner Adapter 与
   三阶段持久消费者已实现；
5. Feature PG 已覆盖幂等、并发 claim、失败保 Raw、成功原子提交、人工 revision/迟到 fence、有限重试与
   recapture 新身份；HTTPX fake 已覆盖派发、retry、cancel 和 settlement 的认证及错误分类；
6. 当前三消费者开关仍为 false，未启动 Backend 8101、真实 Gateway、APK 或设备；独立网关联调与实机仍需
   外部 Owner 精确候选和 ca97 单独授权的一台设备/一个 Douyin 商品/隔离时段。

当前没有 push、PR、CI、dev/main 合并、生产部署、平台真实请求或实机动作。Feature DB 仅含测试期间创建
并由夹具清理的合成记录；三阶段开关保持关闭。
