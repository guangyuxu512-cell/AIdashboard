# 候选池容量基线 V1 Gate 1

## 结论

- 状态：**工具与离线 Gate 1 完成；正式容量验证 BLOCKED_RESOURCE**。
- 分支：`feat/product-selection-capacity-baseline-v1`。
- 精确基线：`9878536849fec3d2d2f1dde811e49957abcba13d`，与建分支时的 `origin/dev` 一致。
- Candidate：本记录所在提交；交接时另附完整 SHA。
- Migration：无变更；源码基线唯一 head 为 `20261015_0046`。
- 业务源码、正式 API、权限、Schema、索引、依赖、前端和 Electron 均未修改。

ca97 已只读确认：现有 Feature、Integration、Main 与生产数据库同属共享 PostgreSQL 集群；本机没有独立 PostgreSQL、Docker 或 WSL 环境。因此本轮没有连接任何数据库或端口，没有造数、EXPLAIN、API 容量请求、浏览器渲染或清理操作。现有 `control_center_feat_product_selection` 明确未使用。

## 交付内容

| 路径 | 用途 |
| --- | --- |
| `backend/tools/product_selection_capacity.py` | 单一显式 CLI：离线计划、分档造数、Repository／正式 ASGI API 测量、受控并发写、EXPLAIN 与精确清理 |
| `backend/tests/test_product_selection_capacity_tool.py` | 确定性分布、契约生成、参数边界、目标保护、namespace／target 绑定和脱敏验证 |
| `docs/engineering/product-selection-capacity-baseline-v1-plan.md` | 冻结的数据分布、测量矩阵、阈值、资源准入与执行顺序 |

工具复用现有 `SelectionResultService`／`SelectionResultRepository`、正式候选查询路由及 `ProductSelectionFactService`。它不加载 ShopSession、不调用 Signer 或平台、不运行 FastAPI lifespan，因此不会启动调度器、采集器或执行器。

## 固定数据与测量范围

- 8 Team，候选比例 40/16/12/10/8/6/5/3%；每 Team 4 Shop，其中 3 个授权、1 个撤权。
- 每 Team 12 策略：3 个授权 Shop × 4 个来源口径。早期 4 策略草案已在 ca97 预审前纠正。
- 每 Candidate 至少 1 个 Observation，约 19% 有第二来源；每 Observation 有当前 ResultItem，约 25% 有历史 ResultItem。
- 覆盖屏蔽、撤权、new／known／unknown、basic succeeded／partial／failed／not-attempted、真实 0／unknown、今日／历史。
- 50k／300k／500k 使用相同固定 seed 和 run UUID；较小档位的 ID 和关系是较大档位的稳定前缀。
- 查询覆盖默认 20／页、首／50%／90%／末页、common／rare／no-result、Shop／撤权／scope／strategy／receipt／今日、三类排序正反向、相邻页和普通 Team／小 Team／super 边界。
- 正式 profile 固定 30 个 warm 样本／case、8 读＋1 个通过正式 FactService 的写入者、至少 60 秒；浏览器 20 行渲染单独验收，不计入 CLI acceptance。

离线 manifest 的最终计数：

| 档位 | Observation | ResultItem | Run | 离线生成耗时 |
| --- | ---: | ---: | ---: | ---: |
| 50,000 Candidate | 59,500 | 74,375 | 264 | 2,703 ms |
| 300,000 Candidate | 357,000 | 446,250 | 824 | 9,494 ms |
| 500,000 Candidate | 595,000 | 743,750 | 1,262 | 15,005 ms |

manifest 位于 ignored 的 `.codex/product-selection-capacity/<run-id>/`；不是数据库或性能通过证据。

## 安全控制

- 数据库名必须匹配 `control_center_capacity_*`，并同时匹配显式 opt-in、精确 endpoint、精确 Migration head 与 run UUID。
- 首次 seed 将 namespace 绑定到目标；后续 measure／cleanup 不能换库、换 endpoint 或换 head。
- 同一 run UUID 持有 PostgreSQL advisory lock，禁止跨进程同时 seed／measure／cleanup。
- statement timeout 默认 8 秒、最大 30 秒；单批默认 1,000、最大 1,500 行；并发最大 16、时长最大 300 秒。
- 造数可按相同 namespace 从 50k 增量扩到 300k／500k；最后一个未满 Run 使用受限 upsert 更新计数，不重复候选。
- 清理只删除确定性 namespace 的关联行，按 1,000 行提交；发现任何跨 namespace 引用即拒绝。无 `TRUNCATE`、`DROP`、日期或名称广域删除。
- 错误输出隐藏数据库参数并二次脱敏 URI 密码、Authorization、Cookie、token 与 secret。

## 实际验证

| 检查 | 结果 |
| --- | --- |
| `python -m pytest tests/test_product_selection_capacity_tool.py -q` | 17 passed |
| `python -m compileall -q app tools tests` | exit 0 |
| Backend 默认 `python -m pytest --tb=short` | 920 passed、378 integration deselected、1 条既有 Starlette/httpx deprecation warning；73.03 秒 |
| `alembic heads` | `20261015_0046 (head)` |
| 50k／300k／500k 离线 `plan` | 全部 exit 0，计数如上 |
| `git diff --check` | exit 0 |

未执行项：独立 PostgreSQL 迁移、seed、Repository／API P50/P95、并发读写、SQL count timing、EXPLAIN ANALYZE、资源水位、浏览器渲染、清理回执。以上全部保持 **NOT_RUN**，不以单测或离线 manifest 代替。

## 精确阻塞与下一负责人

需要 DBAdmin／ca97 提供与生产及现有共享 Feature／Integration／Main 集群隔离的 PostgreSQL 实例：

- 5 万冒烟：至少 4 vCPU、8 GiB RAM、15 GiB 可用磁盘。
- 30 万／50 万正式：至少 8 vCPU、16 GiB RAM、30 GiB 可用磁盘。
- 必需登记：数据库名、endpoint、Migration head、运行 UUID、监控入口、CPU／内存／磁盘／连接水位与停止阈值。

资源到位后由 ca97 先复核目标，再按 50k → 水位确认 → 300k → 水位确认 → 500k → 精确清理执行；81a1 不借用现有数据库继续。本 Candidate 不合 dev／main、不发布生产。
