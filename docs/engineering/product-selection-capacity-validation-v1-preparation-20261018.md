# 候选池容量验证 V1 执行准备与资源 Handoff

## 当前结论

- 状态：`PREPARED / CAPACITY_VALIDATION_BLOCKED_RESOURCE`。
- 分支：`feat/product-selection-capacity-validation-v1`。
- 最新 Green：`1c4d4e30ab100086e078a17fb9338df3bc5216e4`；精确 CI
  `39113258258` 的 verify-offline、frontend-real-build、container-runtime、backend 四项成功。
- 已正常 `--no-ff` 消费独立接受的工具 Candidate
  `1788fd381ef25b44c296aee95470aed6eb12b3f4`；合并提交为
  `1edb9519b7b2e807e8024937169703fbf648d706`，双亲依次为上述 Green 与工具 Candidate。
- 冻结 Git blob：工具 `b429e4ce5050bc97f75c9b9fe67efaff6a16d62a`、测试
  `cb0ef9814a72b8aecee0015865ab8655644377b4`、计划
  `531f7fed1dc551949125951130de19393e45cf2a`。
- 工具 Candidate 的 `TOOL_GATE2_ACCEPTED` 只证明工具边界，不是 5 万／30 万／50 万容量通过。
- Migration Slot：无。本任务不修改业务查询、正式 API、权限、Schema、索引、Migration、依赖、
  Frontend、Electron、Worker 或平台接入。
- 5 万、30 万、50 万的 seed、Repository／API measure、SQL、浏览器与 cleanup 均为 `NOT_RUN`。

原商品数据分支 `feat/shop-product-data-empty-header-v1` 与 Candidate
`d946e5d43a19ffd5d00f7638b3aee3546810dca8` 保留；没有 reset、rebase、清理 Profile、stash 或旧成果。

## 新 Green 兼容结论

- 工具分支与当前 Green 的共同基线为 `f07f6c244573b5891cfbd78f7a48a9ba9227368d`。
- 工具新增的 5 个路径在该基线到当前 Green 之间没有同路径变化，`--no-ff` 合并无冲突。
- 工具依赖的 `backend/app/modules/product_selection`、Access、Shop、User 与 Douyin 选品契约，在共同
  基线到当前 Green 之间没有代码变化；没有重写第二套压测器或适配业务实现。
- 当前 Green 上定向测试：`backend/tests/test_product_selection_capacity_tool.py` 22 passed；工具与测试
  `compileall` exit 0。
- 仅为入口兼容执行一次离线 50k `plan`：本地专用 UUID
  `00000000-0000-4000-8000-000000050018`，日期 `2026-10-18`，默认固定 seed `20261018`。
  结果为 Candidate 50,000、Observation 59,500、ResultItem 74,375、Run 264；ignored manifest SHA-256
  `12985b7a7ea7e49af3ebe7bee1354b528652a92d3fc92a3c196ba43a58d664fc`。这不是正式 run UUID、
  数据库证据或性能结果，不得用于 seed／measure／cleanup。
- 没有重复运行已接受工具的 300k／500k 全套离线验收；分档稳定前缀、固定分布、目标保护、正式参数
  和并发零读／缺写／写失败拒绝仍由原 22 项定向回归保护。

## 正式执行前必填登记

以下字段必须由 ca97／DBAdmin 一次性登记并由执行人逐字复核；任一为空即停止：

| 分类            | 必填字段                                                                    | 当前状态                                                                            |
| --------------- | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| 源码            | 最终 Candidate 完整 SHA、工具 blob、测试 blob                               | blob 已冻结；Candidate SHA 由本分支 Gate 1 Handoff 报告，禁止改用旧工具分支直接运行 |
| 审批            | 容量 run 授权、执行人、DBAdmin、ca97 观察人、允许时间窗                     | `NOT_REGISTERED`                                                                    |
| PostgreSQL 隔离 | 独立实例标识、物理／服务隔离证明、精确 `host:port`                          | `NOT_REGISTERED`；禁止现有共享集群                                                  |
| 数据库          | 精确 `control_center_capacity_*` 名称、最小权限角色标识、受保护配置交付位置 | `NOT_REGISTERED`；文档不得记录密码或 URL                                            |
| Run 绑定        | 正式 run UUID、固定 seed `20261018`、同一上海日期 `as-of`                   | `NOT_REGISTERED`                                                                    |
| Schema          | 执行时实查的唯一 Alembic head、准备方式、只读核验回执                       | `NOT_REGISTERED`；不得从本文硬编码继承                                              |
| 资源            | 分配 vCPU、RAM、可用磁盘、最大连接数、磁盘位置                              | `NOT_REGISTERED`                                                                    |
| 监控            | CPU／RAM／磁盘／连接数入口、采样周期、基线水位、观察人                      | `NOT_REGISTERED`                                                                    |
| 停止阈值        | CPU、内存、剩余磁盘、连接数及持续时间的精确阈值                             | `NOT_REGISTERED`；不得临场猜值                                                      |
| 浏览器          | 独立测量 URL／端口、版本、viewport、执行人、证据目录                        | `NOT_REGISTERED`；不得启动第二 Electron                                             |
| 清理            | 最高已 seed 档位、精确 cleanup 时间窗、清理观察人与完成核对项               | `NOT_REGISTERED`                                                                    |

资源准入下限不替代上述停止阈值：50k 至少 4 vCPU／8 GiB RAM／15 GiB 可用磁盘；300k／500k
至少 8 vCPU／16 GiB RAM／30 GiB 可用磁盘。2026-10-18 本机只读复核为 12 逻辑核、31.87 GiB
总 RAM、仅 2.14 GiB 空闲、D 盘 78.85 GiB 可用，且没有独立 PostgreSQL，因此不是可执行资源。

禁止生产数据库、现有共享 PostgreSQL 集群、原 Feature、Integration 或 Main 数据库；7d55 不自行
建库、安装或启停 PostgreSQL／Docker／WSL、修改 HBA、分配端口或准备管理员权限。

## 固定执行门禁与顺序

1. ca97／DBAdmin 完成全部登记；执行前只读复核源码、`current_database()`、精确 endpoint、唯一
   Migration head、角色边界、监控与空闲水位。配置仅从受保护本地环境读取，不回显。
2. 使用正式 run UUID、固定 seed 和当日上海日期生成 50k 离线 plan；首次 seed 将 namespace 绑定到
   数据库、endpoint 与 Migration head。跨上海午夜不得改 `as-of` 继续同一 namespace；应停止并由
   ca97 决定清理旧 namespace 或登记新 run。
3. 50k seed → 已登记的 smoke profile → 资源水位确认。小于正式参数的结果只能标记 `smoke`。
4. ca97 明确放行后增量 seed 到 300k，执行正式 profile：30 个 warm 样本／case、8 读＋1 写、
   至少 60 秒、writer interval 1 秒、statement timeout 8 秒。
5. 再次确认资源水位后增量 seed 到 500k，使用相同正式参数与同一 namespace 执行。
6. SQL／API／浏览器证据分开验收；全部记录完成后，按最高已 seed 档位执行精确 cleanup。

每一档都禁止自动晋级。目标不匹配、权限／总数／稳定排序／Team 隔离错误、相邻页重复、HTTP 错误、
statement timeout、并发读取为 0、写入结果缺失、成功写入为 0、任一写入失败、跨 namespace 引用或
任一已登记资源停止阈值触发时，立即停止并保留现场；不得重试撞 PASS、降低阈值或临时改业务代码。

## 冻结验收线

| 指标                                           | 正式阈值                                        |
| ---------------------------------------------- | ----------------------------------------------- |
| 权限、总数、分页顺序和隔离                     | 100% 正确                                       |
| HTTP 错误／statement timeout                   | 0                                               |
| 500k warm 常规首／筛选／排序页 API P95         | ≤ 1.5 秒                                        |
| 500k 关键词与 50% 中页／90% 深页／末页 API P95 | ≤ 3 秒                                          |
| 8 读＋1 写混合 API P95                         | ≤ 4 秒                                          |
| 单 SQL statement timeout                       | 8 秒                                            |
| API 返回后浏览器 20 行渲染 P95                 | ≤ 0.8 秒；独立浏览器证据，不计入 CLI acceptance |

未达标时只记录瓶颈、SQL hash、脱敏 EXPLAIN、资源水位和最小优化建议，另行审批；不得在本任务内
擅自加索引、改查询、Schema、API 或验收线。

## 证据分层

| 层              | 必须记录                                                                                                   | 不得替代                                           |
| --------------- | ---------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| 资源            | 每档前后时间戳、CPU／RAM／磁盘／连接基线、峰值、停止阈值事件                                               | 不能用本机硬件总量代替独立实例水位                 |
| SQL             | 脱敏 SQL hash、case、行数／计划行、执行时间、buffers、索引／扫描、statement timeout；EXPLAIN JSON 单独保存 | 小数据 Seq Scan 或 API 总耗时不能直接冒充 SQL 结论 |
| Repository／API | case、30 warm 原始样本、P50/P95、HTTP 状态、total、顺序／去重／隔离、并发读写统计与 acceptance             | 不能把函数单测或离线 manifest 记为 API 性能        |
| 浏览器          | 同档位同源码、浏览器版本、viewport、20 行数据、API 完成点、渲染完成点、已登记样本数的原始值与 P95          | CLI／ASGI 结果不能冒充浏览器渲染                   |
| 清理            | 同 run 删除计数、零残留查询、外部引用检查、manifest 状态及资源回落                                         | 不能用删除本地 JSON 代替数据库清理                 |

原始证据放在 ignored `.codex/product-selection-capacity/<registered-run-uuid>/`，对外 Handoff 仅给
脱敏摘要、相对文件名与 SHA-256；不输出连接串、密码、Token、Cookie、完整敏感参数或原始凭据。

## 命令模板（未登记时禁止执行）

命令均在 `backend` 目录、最终 Candidate 源码中执行。`BACKEND_DATABASE_URL` 只由受保护环境提供。

```powershell
# 50k 离线计划；正式 UUID/as-of 仍需登记
.\.venv\Scripts\python.exe tools\product_selection_capacity.py plan `
  --run-id <registered-run-uuid> --tier 50000 --as-of <shanghai-date>

# 50k 首次 seed；其后 300k/500k 仅替换 tier，保持其余绑定逐字一致
.\.venv\Scripts\python.exe tools\product_selection_capacity.py seed `
  --allow-capacity-test --run-id <registered-run-uuid> --tier 50000 `
  --as-of <shanghai-date> --expected-database <control_center_capacity_name> `
  --expected-endpoint <registered-db-host:port> --expected-head <registered-head> `
  --statement-timeout-ms 8000 --chunk-size 1000

# 300k/500k 正式测量；50k 的 smoke 参数须另行登记，不能冒充 formal
.\.venv\Scripts\python.exe tools\product_selection_capacity.py measure `
  --allow-capacity-test --profile formal --samples 30 --readers 8 --with-writer `
  --duration-seconds 60 --writer-interval-seconds 1 `
  --api-target asgi://product-selection-capacity `
  --run-id <registered-run-uuid> --tier <300000-or-500000> `
  --as-of <shanghai-date> --expected-database <control_center_capacity_name> `
  --expected-endpoint <registered-db-host:port> --expected-head <registered-head> `
  --statement-timeout-ms 8000

# 仅在已登记用例上追加脱敏 EXPLAIN；不对未确认用例临场试跑
# 在上述 measure 命令末尾添加：--explain-case <registered-case-name>

# 最终使用最高已 seed 档位；其余绑定必须与 namespace 完全相同
.\.venv\Scripts\python.exe tools\product_selection_capacity.py cleanup `
  --allow-capacity-test --run-id <registered-run-uuid> --tier <highest-seeded-tier> `
  --as-of <shanghai-date> --expected-database <control_center_capacity_name> `
  --expected-endpoint <registered-db-host:port> --expected-head <registered-head> `
  --statement-timeout-ms 8000
```

## 精确清理规则

- 只使用同一 run UUID、seed、`as-of`、数据库、endpoint、Migration head 和最高已 seed 档位；任何不符
  由工具拒绝，禁止删除或改写 `namespace.json`／`target.json` 绕过。
- cleanup 先检查跨 namespace ResultItem、Run reuse 与 Observation 引用；任一存在即拒绝，不人工解除。
- 仅按确定性 Team／User／Shop／Candidate／Observation／Run ID 删除；ResultItem、Observation、Run、
  Candidate 每批 1,000 行提交，再删除本 namespace 的策略、授权关系、店铺、团队和用户。禁止
  `TRUNCATE`、`DROP`、按名称、日期或模糊条件删除。
- 中断后只允许用完全相同参数重跑，使确定性分批清理继续；不得换 UUID 或另写临时清理脚本。
- 完成条件为工具返回 `state=cleaned`、全部 owned count 为 0、无外部引用，manifest 写入 cleaned／removed
  回执，监控水位回落。ignored namespace、manifest、measure 和 hash 摘要作为证据保留，不清空。

当前停止点：等待 ca97／DBAdmin 完整资源登记与正式放行；此前不执行任何数据库或浏览器容量步骤。
