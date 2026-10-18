# 候选池容量基线 V1 计划

## 边界

- 初始开发基线：`9878536849fec3d2d2f1dde811e49957abcba13d`；工具完成后正常 `--no-ff` 同步精确 Green `f07f6c244573b5891cfbd78f7a48a9ba9227368d`。
- 本任务只提供显式执行的合成数据与测量工具、测试计划和证据；不修改业务查询、权限、API、Schema、索引、Migration 或依赖。
- 不调用抖音、Signer、ShopSession，不启动真实采集、扫描器、Electron 或 PC Worker。
- 仅允许 ca97 登记的独立 PostgreSQL 资源。数据库名必须匹配 `control_center_capacity_*`；生产、dev、Integration、Feature DB 均由工具硬拒绝。

## 固定数据分布

同一固定 seed 和 run UUID 按 5 万、30 万、50 万增量生成，较小档位的 ID 与关系在较大档位保持不变。

| 项目 | 分布 |
| --- | --- |
| Team | 8 个，候选比例 40/16/12/10/8/6/5/3% |
| 用户 | 每 Team 1 个普通用户；另 1 个仅用于跨 Team 读取验证的超级账号 |
| 店铺 | 每 Team 4 个；3 个保持授权，1 个保留事实但不授权 |
| 策略 | 每 Team 12 个（3 个授权店铺 × 4 个来源口径）；包含每小时／每日配置，仅作为查询数据，不启动调度 |
| Candidate | 5% 屏蔽；商品 ID 全程字符串；标题含 common、rare、no-result 可验证分布 |
| Observation | 每商品至少 1 个；约 19% 有第二店铺／来源口径 Observation（撤权店铺样本不再生成第二来源） |
| Run / ResultItem | 按 Team／Shop／来源口径分组，每 1000 个 Observation 封一个当前终态 Run；历史命中另建对应历史 Run。策略／手动混合；每 Observation 有当前结果，约 25% 另有历史结果 |
| 状态 | 覆盖 new/known/unknown、真实 0、未知、basic succeeded/partial/not-attempted、今日与历史命中 |

离线清单的确定性计数如下；它们是造数计划，不是 PostgreSQL 已完成证明：

| 档位 | Candidate | Observation | ResultItem | Run |
| --- | ---: | ---: | ---: | ---: |
| 5 万 | 50,000 | 59,500 | 74,375 | 264 |
| 30 万 | 300,000 | 357,000 | 446,250 | 824 |
| 50 万 | 500,000 | 595,000 | 743,750 | 1,262 |

5 万冒烟准入至少需要 4 vCPU、8 GiB RAM、15 GiB 可用磁盘；30 万／50 万正式测试需要独立实例至少 8 vCPU、16 GiB RAM、30 GiB 可用磁盘，并由 DBAdmin 提供 CPU、内存、磁盘、连接数监控与停止阈值。实际水位由 ca97 在每档前后确认。

## 测量用例

测量必须走现有 `SelectionResultService` / `SelectionResultRepository` 和正式 `GET /api/v1/product-selection/candidates`：

1. 默认 20 条／页：首、中、90% 深页及末页。
2. common、rare、无结果关键词。
3. Shop、屏蔽、策略、receipt/batch、今日 new/known/all。
4. `checked_at`、`first_on_shelf_date`、`rank` 正反排序及组合筛选。
5. 普通 Team、撤权 Shop、跨 Team、超级账号读取边界。
6. 相同请求重复读取的 total、稳定排序、相邻页去重。
7. 受控并发：最多 8 个读取者和 1 个合成写入者；写入者只通过正式 FactService 更新固定 10 个本 run 商品。

首样本定义为“新进程首个 API 请求”，不声称 PostgreSQL buffer 被清空；其余每个 case 的首个样本只叫 first sample。正式 profile 每个 case 固定采集 30 个 warm 样本，8 读＋1 写持续至少 60 秒。API、SQL 和浏览器渲染证据分开记录；未执行的层明确写未覆盖。

## 预先冻结的建议阈值

| 指标 | 阈值 |
| --- | --- |
| 权限、总数、分页顺序和隔离 | 100% 正确 |
| HTTP 错误／statement timeout | 0 |
| 50 万 warm 常规首／筛选／排序页 API P95 | ≤ 1.5 秒 |
| 50 万关键词与 50% 中页／90% 深页／末页 API P95 | ≤ 3 秒 |
| 8 读 + 1 写混合 API P95 | ≤ 4 秒 |
| 单 SQL statement timeout | 8 秒 |
| API 返回后浏览器 20 行渲染 P95（独立浏览器证据，不计入 CLI acceptance） | ≤ 0.8 秒 |

若阈值未达到，记录实际瓶颈、SQL hash、脱敏 EXPLAIN 与最小优化建议，另行审批；不得修改阈值制造 PASS。

## 安全控制和执行顺序

- `plan` 完全离线；其他命令必须同时提供 opt-in、run UUID、精确数据库、精确 endpoint 和精确 Migration head。
- 首次 `seed` 会把 run namespace 绑定到脱敏的数据库名、endpoint 和 Migration head；后续测量／清理若目标不同会直接拒绝。
- 每个数据库命令持有基于 run UUID 的 PostgreSQL advisory lock；同一 namespace 的造数、测量和清理不能跨进程并行。
- `measure` 的 `as-of` 必须等于执行时的上海日期，确保“今日”查询有可验证的确定语义。
- 正式 profile 硬性要求每 case 30 个 warm 样本、8 个读取者、1 个受控写入者和至少 60 秒；较小参数只能标记 smoke。
- 并发 acceptance 要求实际完成至少 1 个读取请求；启用写入者时还要求写入结果存在、成功写入数大于 0 且失败数为 0。零请求或写入全失败不能因 P95 默认为 0 而通过。
- 并发上限 16、时长上限 300 秒、statement timeout 上限 30 秒；正式计划使用更小的冻结值。
- 单批最多 1,500 行，默认 1,000 行，避免 Observation 多列写入超过 PostgreSQL bind 参数上限。
- 清理只按本次 run UUID 确定生成的 Team/User/Shop 与关联行删除；无 `TRUNCATE`、`DROP` 或广域日期／名称删除。
- 50 万清理按 1,000 行提交，可中断续跑；发现任何跨 namespace 引用立即拒绝。
- 运行顺序：离线计划与单测 → 5 万冒烟 → 资源水位确认 → 30 万正式 → 再确认 → 50 万正式 → 精确清理。
- EXPLAIN ANALYZE 仅在已确认的容量数据库、指定用例执行；不加入日常快速 Verify。

## 命令边界

```powershell
# 唯一无需数据库的命令
.\.venv\Scripts\python.exe tools\product_selection_capacity.py plan `
  --run-id <registered-run-uuid> --tier 50000 --as-of <shanghai-date>

# 以下占位符必须由 ca97 登记后逐字替换；未登记时禁止执行
.\.venv\Scripts\python.exe tools\product_selection_capacity.py seed `
  --allow-capacity-test --run-id <registered-run-uuid> --tier 50000 `
  --as-of <shanghai-date> --expected-database control_center_capacity_<id> `
  --expected-endpoint <dedicated-host:port> --expected-head <registered-exact-head>

# 300k/500k 正式测量协议；50k 可先用 smoke profile 做准入冒烟
.\.venv\Scripts\python.exe tools\product_selection_capacity.py measure `
  --allow-capacity-test --profile formal --samples 30 --readers 8 `
  --with-writer --duration-seconds 60 --api-target asgi://product-selection-capacity `
  --run-id <registered-run-uuid> --tier <300000-or-500000> `
  --as-of <shanghai-date> --expected-database control_center_capacity_<id> `
  --expected-endpoint <dedicated-host:port> --expected-head <registered-exact-head>
```

`--expected-head` 必须使用容量实例执行时由 ca97／DBAdmin 登记并实查的唯一 Migration head，不能从文档示例固定继承。当前同步 Green 的源码 head 是 `20261017_0047`，但未来专用实例仍以执行前实查登记值为准。

`measure` 只接受进程内正式 ASGI 目标 `asgi://product-selection-capacity`，不会向外部 HTTP 地址发请求；所有平台请求计数固定为 0。工具为连接设置 `application_name=product-selection-capacity`，便于 ca97 从专用实例观察并中止。CLI 只判定 Repository／API／并发阈值；浏览器 20 行渲染由 ca97 在同一数据档位另行测量并单独记录。

## 当前资源结论（2026-10-18）

ca97 只读核验确认：现有 Feature、Integration、Main 和生产数据库均位于共享 PostgreSQL 集群，本机没有独立 PostgreSQL／Docker／WSL 运行环境。因此目前只能执行离线 `plan` 和单元测试；5 万、30 万、50 万造数及正式 SQL/API/浏览器测量均未执行。待 DBAdmin 或 ca97 提供独立实例、精确 endpoint、数据库名、执行时精确 Migration head、监控及停止阈值后，才可进入 5 万冒烟。
