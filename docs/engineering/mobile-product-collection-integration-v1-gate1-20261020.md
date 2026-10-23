# 手机商品资料采集真实接入 V1 Gate 1

## 基线、资源与结论

- Feature Owner：81a1；分支：`feat/mobile-product-collection-integration-v1`；精确 Green / 起点：
  `65ecf3f72a6ae9ea3114d7404841ad9aae876565`。最终 Candidate 以正式 Handoff 的完整 SHA 为准。
- ca97 已登记 Feature PostgreSQL：`control_center_feat_mobile_product_collection_integration`，最小角色
  `control_center_dev_user`，受保护隧道 `127.0.0.1:35433`，Backend 资源 `8101`。
- 唯一 Migration 为 `20261020_0049`，down=`20261019_0048`。0049 已在 Feature 库完成
  upgrade、空库 downgrade、再次 upgrade；最终复核数据库 Head 精确为 0049。
- 中控侧持久化闭环、人员 API、服务 API、网关窄适配、UU cleaner 窄适配及三个持久消费者已经完成
  Gate 1。真实网关／collector APK／一台设备闭环仍须由 ca97 与外部 Owner 使用精确配对候选、独立授权
  和隔离时段完成，不能以本 Gate 的合成或 PostgreSQL 证据替代。
- 没有启动 Backend、Frontend、Electron、Gateway 或设备；没有平台真实请求、生产连接、push、PR、CI、
  dev/main 合并或部署。三个消费者开关保持 `false`。

## 已完成实现

### 人员业务与权限

- `POST /api/v1/product-collection/requests` 支持手工商品标识和当前 Actor 可见的选品候选；Team 只来自
  `ActorContext`，候选逐项复用既有可见性查询，submission key 同 payload 幂等、不同 payload 冲突。
- Douyin 进入自动网关关系；PDD 只登记人工回传边界；Taobao／未知平台 fail-closed。
- 请求列表／详情、取消、有限 retry、显式 recapture、商品库分组只读、商品分页列表和详情均在正式
  `API → Service → Repository → PostgreSQL` 边界内执行，查询在聚合和分页前落实 Team 隔离。
- retry 复用原 Dispatch / external job identity 并累计尝试；只有显式 recapture 新建 Dispatch，历史记录不删。

### 既有网关、手机接收与双回执

- 中控只保存可靠派发关系，不建立第二套手机 claim 队列。网关调用严格使用已冻结的 camelCase V1
  dispatch/retry/cancel/settlement 契约，control、callback、gateway-service、批次 ingest credential 四类认证分离。
- claim 后由网关注册 `job + device + capture batch`；中控以 256-bit 以上 HMAC key 派生短期 opaque
  credential，数据库只保存 salt/hash/key id/版本/时限。相同批次注册及相同内容上传幂等；不同内容、旧批次、
  身份不一致或过期凭据拒绝。
- 手机完整包先在短事务内可靠保存 Raw 并返回 202 `received`；后台在事务外调用既有
  `convertCompletePackage()`，再以短事务提交不可变 Version、当前 Product、Persist Receipt 及统一结算 outbox。
- 若 202 在网络中丢失，同一合法 credential 在有效时限内重放同 content hash，即使后台已进入
  persisted/failed/superseded，也稳定返回原 `receiptId + duplicate`；不同 hash 仍为 409。服务先做凭据
  预校验再解析 JSON，并在加锁后复核，错误或过期凭据不能借既有 Receipt 查询结果或消耗解析资源。
- Raw payload 在进入 JSONB 前有大小、深度、字符串、URL、有限顶层和凭据键约束；Cookie、Authorization、
  Token、签名或含凭据的完整 URL 不会进入业务表、日志和文档。商品／SKU／Job／Device／Batch ID 全程字符串。
- cleaner 子进程只获得 Node 启动所需的最小系统环境，不继承数据库连接、网关 token、ingest HMAC key
  或其它 Backend 服务配置；该约束由拦截 subprocess 的定向测试验证。
- 图片 URL 只允许部署 allowlist 的 HTTPS host，并删除 userinfo、签名、token、expiry/auth query；未知价格为
  `null`，有明确证据的真实 0 保留为 0；可见小数价格不会因整数截断被错误转换。

### 持久化、并发与恢复

- 0049 增加 Team 商品库、不可变版本、业务 Request/Item、Dispatch、Capture Attempt、Upload Receipt、
  Persist Receipt 共九表，并只为既有候选补 `(candidate_id, team_id)` 唯一目标；0042–0048 未改写。
- Claim 使用 PostgreSQL `FOR UPDATE SKIP LOCKED`、partial unique、lease 和 fence；平台／网关／cleaner I/O
  均在事务外。迟到批次、人工 revision 变化和更旧 captured-at 均不能覆盖当前事实，但保留版本证据。
- 清洗确定性失败进入 `failed + settlement pending`，保留 Raw 且不伪造 Persist Receipt；进程中断只在
  processing lease 到期后恢复。新增真实 PostgreSQL 验证证明新执行者取得新 lease，旧执行者被 fence 拒绝，
  最终仅提交一次版本。
- 派发进程在最后一次 `delivering` 租约中断时，由下一次数据库扫描提交
  `PRODUCT_COLLECTION_GATEWAY_DELIVERY_INTERRUPTED` 终态并同步 Item/Request；不会回滚恢复结果、重置
  尝试次数或永久卡在执行中。
- 网关结算 outbox 按持久 attempt budget 有限重试；进程在最后一次 delivering 中断时会转成显式 exhausted
  failure，不会永久卡住。派发、处理、结算三个循环独立，任一阶段暂时无任务不阻塞其他阶段。
- 结算响应的 `jobStatus` 使用网关完整既有状态枚举；旧批次 superseded 时允许当前 Job 已进入
  pending/running/captured，不要求网关伪报 retry_wait，仍严格校验 gatewayJobId/captureBatchId 和非法状态。
- Backend 启用任一消费者但缺少该阶段受保护配置时启动 fail-closed；外部 HTTP/cleaner timeout 必须小于
  对应数据库 fence。禁用状态不会构建外部适配器或打开数据库连接。

## Schema 与回滚

- Feature DB 最终复核：数据库名、最小角色、Head 0049 均正确；九张新表均为 0 行；execution、processing、
  settlement 三开关均为 false。
- 针对九表及 `uq_selection_candidate_id_team` 的 metadata 比较为 `product_collection_drift_count=0`。
- 全仓 `alembic check` 仍为 exit 1，只包含仓库既有的非本功能漂移：旧表 CHECK constraint 命名、
  `platform_credentials/shops` enum 类型表示和 `worker_device_credentials` 旧 unique/index 表示；未把这些存量
  问题混入 0049。
- 0049 downgrade 只允许精确登记的空 Feature DB，并在锁表后逐表 fail-closed 检查；Integration／共享／
  生产回滚必须先关闭入口和三个消费者、回退应用镜像并保留 Schema、Raw、版本和审计，不能清表降级。

## Gate 1 验证

| 检查 | 结果 |
| --- | --- |
| Product Collection 定向单测 | 42 passed；API、凭据键拒绝、NaN/Infinity、网关认证／错误分类、完整结算状态读取、cleaner、Model、消费者配置和阶段隔离通过；仅既有 Starlette/httpx warning |
| Feature PostgreSQL 0049 | 13 passed；唯一/FK/CHECK、真实零、失败保 Raw、原子成功、Team/候选隔离、幂等、并发上传、终态同内容稳定重放、错误/过期凭据拒绝、dispatch retry/recapture、人工/迟到 fence、结算有限重试、processing lease 重启恢复及最终派发租约中断终态化通过 |
| Backend 默认完整回归 | 1127 passed、472 integration deselected；仅既有 Starlette/httpx warning |
| Node 24.19 / pnpm 11.25 `pnpm verify` | exit 0；10 Node 负测、2 Python AST、正式 ASGI probe、Frontend contract 9 passed；0 known/new/stale |
| Node 24.19 / pnpm 11.25 `pnpm verify --full --only=backend` | exit 0；1123 passed、472 deselected；4 个原 CI 保留的开端口测试明确 NOT_RUN；0 known/new/stale |
| Python / diff | Product Collection、Settings、Main `compileall` exit 0；`git diff --check` exit 0 |
| Migration | `alembic current`=`20261020_0049 (head)`；本功能 drift 0；全仓 check 仅上述存量非 Feature 漂移 |

第一次从仓库根目录调用 `./.venv/Scripts/python` 的 compileall 因工作目录错误未找到解释器；随后在
`backend` 使用同一登记 venv 原样重跑并通过。早期 shell 默认 Node 20 不满足 `node:sqlite`／pnpm 11
运行门槛；最终证据全部使用仓库已有 Node 24.19 / pnpm 11.25，未修改依赖、lock 或 CI。

## 未执行边界与 Gate 2 交接

- 未执行真实 Gateway、真实 collector APK、设备 claim/heartbeat/上传、真实 Douyin 商品、NAS、外部服务或
  Electron；也未消费冻结但非 Green 的前端候选。当前交付不能标成“实机真实闭环完成”。
- ca97 Gate 2 需先核对中控 Candidate 与外部 Owner 精确候选的协议字节，再在隔离环境验证
  `中控 → 既有网关 → 手机替身 → 中控`，确认 202 received 与 persisted/settled 分离。
- 真实设备只在另行确认的一台设备、一个 Douyin 商品、隔离时段及恢复计划下执行；PDD 只验人工边界，
  Taobao 不测。任何配对差异退回对应 Owner，不在 Integration 工作树补写业务实现。
- 发布顺序：0049 → 部署且三开关保持关闭 → 配对闭环和 Release Gate → 写入持久化受保护配置并重启。
  Owner 81a1 不合并 dev/main、不部署；私有仓库未获安排前不 push/PR/触发 CI。

## 2026-10-20 中控／网关 HTTP 适配增量

- 配对基线为中控 `fb25a53fdb3448427843e501a636d356307153d1` 与只读网关
  `391e88100bc9dd85322f8a8ae1264f8b463ca6df`。本增量不修改 Gateway、Collector、APK、手机、
  Migration、业务 Schema、消费者配置或其它模块。
- 中控入口同时接受历史紧凑 V1 与 Collector 0.4.10 实际原始 V2；V2 使用明确顶层 allowlist，
  三个 SHA-256 字段严格要求 64 位小写十六进制。修前网关配对脚本证明 `not-a-sha256` 会被接受；
  修后同一脚本保留全部实际 V2 字段并逐项拒绝三个非法哈希。
- 相同 attempt／gateway／device／job／batch／credential identity 在 `accept_until` 内的刷新是确定性
  重发：credential ID、version、salt 派生 token 均不轮换，只延长服务端有效期。刷新响应丢失可用原
  credential ID 重放；Raw 已持久接收但 202 丢失时，刷新后同内容返回原 receipt 的 `duplicate`，
  不同内容仍返回冲突。错误 identity、过期窗口、canceled 或无 Receipt 的非活动 attempt 不会复活。
- 定向结果：Product Collection 非 PG 49 passed；实际网关 DTO 配对脚本 passed；Feature PG 两条精确
  刷新／重放用例 passed；compileall 与 `git diff --check` passed。Feature 库 Head 仍为 0049，三个消费者
  开关均 false，定向执行前活动 Dispatch／Attempt／Upload／Settlement 均为 0。
- 额外运行完整 Product Collection PG 文件时，两项全局 claim 用例受到本机既有 8101 后端进程竞争，
  分别未取得 Settlement／Inbox claim；本增量的两条精确用例单独运行通过。未停止或重启既有服务，
  未为消除环境竞争修改队列实现或放宽测试。
