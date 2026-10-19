# 商品数据多店持久队列 V1：最小结构与资源提案

## 状态与边界

- Owner：81a1；技术审核、资源登记与 Gate 2：ca97。
- 精确 Green：`915c9d147276aa7bfcd3dabf1385c670c5696c6c`。
- 分支：`feat/shop-product-data-batch-queue-v1`。
- 当前已发布商品数据 Migration：`20261017_0047`，保持字节不变。
- ca97 已于 2026-10-19 通过本提案并登记：Migration `20261019_0048`
  （down revision `20261017_0047`）、独立库 `control_center_feat_shop_product_data_batch_queue`、
  受限角色 `control_center_dev_user`、数据库隧道 `127.0.0.1:35433`、Backend `8103`、
  Frontend `4178 --strictPort`。0048 已在登记 Feature 库应用并完成空库往返及 0047 事实往返；
  这仍不等于 Integration、Gate 2、生产迁移或部署。
- 范围只包含“数据中心 → 商品数据”的手动多店更新与后台持久执行。不会加入每日计划、
  选品、商品库、手机任务、经营采集、Redis、Celery 或新的通用队列框架。
- 生产开关、生产并发和生产数据库均不在本阶段变更范围内。开发与集成默认关闭真实执行。

## 为什么必须有 0047 之后的新 Migration

0047 只有商品、口径序列、采集代次和指标快照四张表。代次由 HTTP 请求直接启动，
缺少一次多店提交的稳定身份、等待领取状态、租约心跳、超时恢复和同店串行的数据库约束。
0047 还含有：

- `uq_spd_generation_actor_key`：幂等键落在单店代次，不能表达“一次提交包含多店”；
- `uq_spd_active_slice`：同店同口径只允许一个 pending/running，无法保存多个合法待执行意图；
- 旧 `state_fields`：没有 pending、attempt、heartbeat 等持久队列状态语义。

因此本功能不能只改 Python 领取逻辑，也不能继续借旧 0047 Feature 库验证。ca97 已据此在
0047 之后登记 0048，并分配独立 Feature 数据库、Backend 端口和 Frontend 端口；实现和验证只使用
这些精确资源。

## 最小 Schema 变化

### 新表 `shop_product_data_collection_batches`

| 字段 | 语义 |
| --- | --- |
| `collection_batch_id` | 一次多店提交的稳定 UUID |
| `requested_by_user_id` | 原始提交人，`RESTRICT` 关联用户 |
| `requested_team_id` | 提交时团队上下文，可空，`RESTRICT` 关联团队 |
| `submission_key` | 客户端重放幂等键 |
| `period` / `sale_type` / `content_type` | 本批次冻结的原生请求口径 |
| `created_at` / `updated_at` | 审计时间 |

约束：

- `UNIQUE(requested_by_user_id, submission_key)`，同一用户重放返回原批次；
- 口径仍只允许已验证的 `1d/7d/30d`、`sale_type=1`、`content_type=1`；
- 批次不存 Cookie、Token、签名或完整敏感 URL。

批次总体状态和成功／失败／等待数量由其代次实时投影，不新增第二套状态机。

### 扩展 `shop_product_data_generations`

新增：

- `collection_batch_id UUID NOT NULL`，`RESTRICT` 关联批次；
- `batch_position INTEGER NOT NULL`，保存提交中稳定顺序；
- `attempt_count INTEGER NOT NULL DEFAULT 0`；
- `last_heartbeat_at TIMESTAMPTZ NULL`。

替换／新增约束与索引：

- `UNIQUE(collection_batch_id, shop_id)`；
- `UNIQUE(collection_batch_id, batch_position)`；
- partial unique `shop_id WHERE status='running'`，把同店串行落实到数据库；
- 队列索引 `(status, created_at, generation_id)`；
- 批次读取索引 `(collection_batch_id, batch_position)`；
- 保留原 actor、series、source scope、完整快照和事实唯一约束。

移除：

- 旧 `uq_spd_generation_actor_key`；批次级重放由新表负责；
- 旧 `uq_spd_active_slice`；多个不同提交可以排队，但同一时刻仍只有一个同店 running。

状态约束冻结为：

- `pending`：未领取、`attempt_count=0`、无 lease/heartbeat/start/finish/publish；
- `running`：`attempt_count>0`，lease、heartbeat、started 均存在；
- `succeeded`：无活动 lease，heartbeat/start/finish/publish 均存在，分页覆盖完整且无失败码；
- `failed`：无活动 lease，heartbeat/finish 和失败码存在，不发布半截事实。

### 0047 旧数据回填

升级不能删除、重写或伪造已有商品事实。对每条已有 generation 创建一个一对一的兼容批次：

- `collection_batch_id` 使用该 generation 的 `generation_id`，形成确定性映射；
- 批次复制原 `requested_by_user_id`、`requested_team_id`、`submission_key`、口径和审计时间；
- generation 关联该批次，`batch_position=0`；
- 旧 `running/succeeded/failed` 的 `attempt_count=1`；只有真正的旧 pending 才为 0；
- 旧非 pending 行的 `last_heartbeat_at` 使用已有 `updated_at/started_at/created_at` 中最具体的
  安全时间，不改变原开始、结束、发布或 lease 值；
- 先建可空列和新表、完成回填与一致性核验，再设 NOT NULL、替换旧约束并创建新索引。

升级前需显式核验：旧 `(requested_by_user_id, submission_key)` 无冲突、旧 running 同店不超过一条、
旧行均满足可转换状态。任一不满足即拒绝升级，不自动清理数据。

### 降级与恢复

已产生真实多店批次、排队意图、重复尝试或恢复历史后，不能安全还原为 0047 单代次语义。
Migration 的 downgrade 只允许在精确登记的可重建 Feature 数据库，并逐项满足：

1. 每个批次恰好关联一个 generation，且 `batch_position=0`；
2. 批次与 generation 的提交人、团队、submission key、period、sale/content type 全部一致；
3. `attempt_count` 仍等于旧语义可表达的值（pending 为 0，其余为 1），没有超时恢复或重复领取；
4. 所有行重新满足 0047 的 `uq_spd_generation_actor_key` 和 `uq_spd_active_slice`；
5. 删除批次关联后不会丢失任何真实审计关系。

任一条件不满足即明确拒绝。Integration/生产采用向前修复和兼容旧读路径，不通过降级、清库或
删除队列历史恢复。

部署恢复优先关闭 `PRODUCT_DATA_COLLECTION_EXECUTION_ENABLED`，保留提交、批次、代次和已发布事实，
再回滚应用镜像到仍能读取新 Schema 的兼容版本。不能把“关闭消费者”描述成可以任意回滚到 0047 代码。

## 事务、领取与并发契约

### 提交

1. 一次请求只接受 1–100 个互不重复的店铺 UUID；重复 `shop_id` 明确拒绝，不静默去重。
   通过校验后冻结一次日期和口径，创建一个批次和每店一个 pending generation；
2. 所有店铺权限、启用／删除状态和平台支持性在写入前检查；无权店铺不能进入批次；
3. 同一 actor + submission key 重放返回原批次，不创建空批次或重复代次；
4. HTTP 返回异步批次标识，不等待平台请求。

### 跨进程领取

领取使用仅限商品数据域的 PostgreSQL transaction advisory lock，短事务内完成：

1. 回收 lease 已过期的 running（增加 attempt、换新 lease 后重新执行）；
2. 统计未过期 running 数，严格受 `product_data_collection_max_running` 限制；
3. 从 pending／可恢复行按 `created_at, generation_id` 稳定排序，使用 `FOR UPDATE SKIP LOCKED`；
4. SQL 层排除已有 live running 的 shop，忙店不得挡住后面的空闲店；
5. 写入 running、lease、heartbeat、started 后提交。

运行参数冻结如下：

| 配置 | 默认值 | 允许范围 | 说明 |
| --- | ---: | ---: | --- |
| `product_data_collection_max_running` | 1 | 1–5 | 商品数据域全局并发；目标验收上限为 5 |
| `product_data_collection_max_pages` | 101 | 1–500 | 每页固定 10 条；默认最多 1,010 条，足以完整发布 1,001 条样本 |
| `product_data_collection_lease_seconds` | 600 秒 | 60–3,600 秒 | 每页前后续租；超时后可由其他进程恢复 |
| `product_data_collection_scan_interval_seconds` | 1.0 秒 | 0.1–60 秒 | 仅扫描已提交任务，不创建自动计划 |

第一页已返回的 `total` 如果超过 `max_pages * 10`，立即以安全的覆盖上限失败，不请求第二页；
旧成功快照和 current pointer 保持不变。多进程共享数据库锁和约束，不能各自突破并发上限。
本功能不创建跨业务 Shop 锁，不影响经营采集、选品或 PC 任务的并发语义。

### 平台 I/O、心跳与 fence

- Session 获取、Signer、HTTP 和分页均在事务外执行；每页前后用短事务续租并验证 lease；
- 实际发送哪些 Cookie，就使用同一组 Cookie 参与签名；签名后复用同一请求；
- 执行前和发布前复核提交人、团队、模块、店铺授权及店铺启用／删除状态；
- lease 丢失或过期执行者只停止，不能更新 Session、进度、失败状态或覆盖新执行者结果；
- 最终所有页、完整性校验、商品／快照写入、generation 终态和 series current pointer 在一个短事务原子发布；
- 任意分页／解析／补充失败不更新 current pointer，旧成功快照继续可读。

消费者常驻 Backend，由独立 worker 数量匹配配置容量。应用退出时立即取消扫描协程并停止新领取，
退出等待边界为 **0 秒额外业务等待**：已经发出的同步 HTTP/Signer 调用不能被 Python 线程可靠撤销，
因此不声称取消它，也不为了它阻塞 lifespan。平台 HTTP 自身仍使用既有 15 秒有限超时；任何迟到结果
必须通过 lease fence，失去 lease 后不能写 Session、进度、终态或事实。pending/running 记录保留，
重启后过期 lease 由正式领取路径恢复，不依赖 Electron 或浏览器存活。

## API 与权限边界

- 保留单店提交／查询 API，内部包装为一店批次，兼容旧前端与调用方；
- 新增可采集店铺查询、多店批次提交和批次进度查询；
- 列表店铺和提交店铺均先按既有模块／团队／店铺授权过滤；同一店铺不会因多团队授权重复；
- 普通用户只能读取自己在相应团队提交且仍拥有全部目标店铺访问权的批次；超级账号仍校验资源存在；
- 执行时再次检查权限，撤权、停用或删除会安全失败该店任务，不影响其他店；
- 进度按店铺显示 pending/running/succeeded/failed、阶段与脱敏失败码，不返回敏感平台上下文。

前端关闭后任务继续。再次打开时通过批次 ID 读取数据库进度；筛选、分页和读取商品数据不触发采集。

## 已登记资源

ca97 已按审核结果分配且仅分配：

1. `20261019_0048_shop_product_data_batch_queue_v1.py`，down revision 为 `20261017_0047`；
2. 独立 Feature PostgreSQL 数据库 `control_center_feat_shop_product_data_batch_queue`，
   使用 `control_center_dev_user` 受限角色和本机 `35433` 受信任隧道；
3. 独立 Backend `8103` / Frontend `4178 --strictPort`；
4. 五个明确配置值：执行开关、最大并发、最大页数、lease 秒数、扫描间隔。
   Feature 初始执行开关必须 false。

不复用已退休的 `control_center_feat_shop_product_data`，不借 Integration／生产数据库，不使用其他
Feature 的端口或 Slot。PG 护栏必须同时核对上述数据库名、角色、host 和端口后才允许连接。

## Gate 1 验收矩阵

### 无数据库／合成平台

- 多店请求日期只冻结一次，提交重放返回同一批次；
- 旧单店 API 仍返回兼容回执；
- 1／100 店输入边界、101 店和重复店铺明确拒绝、权限过滤、停用／删除零平台调用；
- 最多 5 个消费者，取消时所有消费者已完成首轮，不用 sleep 竞态削弱断言；
- 默认 101 页完整发布 1,001 条；1,011 条在第一页安全失败、没有第二页请求，旧成功 pointer 不变；
- 空结果、解析失败和中途失败均不发布半截快照；
- heartbeat/fence、迟到成功／失败、Session 更新均不能越过丢失 lease；
- Frontend 一次提交多店、重复点击防抖、关闭后重开进度、逐店状态及 Real 不回退 Mock。

### 独立 Feature PostgreSQL（资源分配后）

- 新 Migration 升级、允许条件下的降级／再升级、模型与 frozen migration 精确一致；
- 0047 旧行回填无损，真实事实、series pointer 和审计时间保持；
- actor+submission、batch+shop、batch+position、同店 running、状态 CHECK 的正负例；
- 两进程并发提交不重复；两进程领取不突破全局容量；同店串行、不同店并行；
- 忙店不阻塞空闲店，超时 recovery 只产生一个新 lease，旧 executor 被 fence；
- 外部请求确认不在数据库事务中，失败不覆盖旧成功；
- 跨团队批次读取、撤权后的执行复核、停用／删除零平台 I/O；
- 100 店同到达使用合成平台，验证稳定排队与逐个释放，不进行 100 次真实平台请求。

### Gate 1 明确不包含

- 生产真实平台批量调用、生产并发开关或生产迁移；
- Integration Electron、Gate 2、dev/main 合并、CI 或部署；
- 每日自动采集、商品库、选品、手机任务或跨业务队列。

## 当前状态与下一责任人

81a1 已完成 0048、队列／消费者、批次 API、前端多店进度与恢复实现，并在登记 Feature PostgreSQL
完成空库 0048→0047→0048、0047 旧事实往返、约束、并发／恢复和 100 店持久排队验证。实现提交为
`bade8bca4d2b959e9029272c1dfe82b75eea590b`；用户命名增量返修提交为
`7be04375b01adf449ab42b6073fbe1ad0a21ebb2`。Gate 1 已按同目录交接记录收口，下一责任人为 ca97
独立 Gate 2。该状态不代表已合并 dev/main、执行 CI、调用真实平台或部署生产。
