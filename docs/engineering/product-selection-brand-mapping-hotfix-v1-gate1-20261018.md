# 选品品牌映射热修 V1 Gate 1

## 结论与范围

- 精确 Green：`a6df9ac43b0987b68bd13313ab40d2aeca84c63d`；分支：
  `hotfix/product-selection-brand-mapping-v1`。
- 本次只纠正罗盘品牌查询映射：不限 `-1`、知名品牌 `1`、非知名品牌 `0`。
- 新非默认品牌请求冻结为 v9。手动、保存策略后的执行、定时执行、主窗、备用窗、分页和最终
  Query 均使用同一映射；`0` 不会因 truthy 处理变回不限。
- 历史 v7/v8 继续按当时实际发送的 `known=0`、`unknown=1` 读取；旧 JSON、fingerprint、
  来源事实和审计均不改写。旧 submission key 重放仍返回旧冻结请求，新 submission 不复用旧映射 Run。
- 无前端、Schema、Migration、配置或依赖变化；不处理候选池、定时 B、0047 或其它业务。

标签方向来自用户对官方页面的最新确认；受忽略的同条件只读证据只用于证明 `0`、`1` 的返回集合
确实不同，不能单独推断标签。证据文件已由 `.codex/git-exclude` 排除，不进入 Git、日志或本报告。

## 实现与兼容

`SelectionResolvedRequest` 增加 v9 Reader/Validator。v9 保存纠正后的实际品牌值和目标页；校验时仅创建
不持久化、不签名的默认品牌投影，以复用既有日期和价格约束。历史 v8 的稀疏页投影仍落到历史 v7，
因此保持旧值解释。执行器、策略关联、日期选择和来源写入显式接受 v9；精确业务码探查白名单仍只含
原默认品牌版本，非默认品牌没有扩大重试。

恢复要求：写入 v9 后不能部署不认识 v9 的旧 Backend。若需暂停，使用既有执行开关停止新提交/领取，
保留兼容 Reader、Schema、Run 和事实；不得清库、降级迁移或重写历史品牌值。

## Gate 1 证据

| 检查 | 结果 |
| --- | --- |
| 修前定向测试 | 新硬编码映射、最终 Query、v9 与旧版本兼容断言按预期失败；证明用例可捕获原反向映射 |
| `pytest tests/test_selection_brand_mapping.py tests/test_selection_target_pages.py -q` | 72 passed |
| `pytest tests -k selection -q` | 295 passed；仅既有 Starlette/httpx warning |
| `pytest -q` | 874 passed、378 integration deselected；仅既有 Starlette/httpx warning |
| `python -m compileall -q app tests` | exit 0 |
| Node 24.19 / pnpm 11.25：`pnpm verify` | exit 0；28 known、0 new、0 stale |
| 同环境 `pnpm verify --strict` | 预期 exit 1；仅 28 个既有严格差异，无新增或 stale |
| `pnpm verify --full --only=backend` | exit 0；874 passed、378 integration deselected；28 known、0 new、0 stale |
| `git diff --check` | exit 0 |

首次从普通 PowerShell 运行 Verify 时命中 Node 20.18，预装 pnpm 11.25 因缺少 `node:sqlite` 退出，
并产生不可信的 stale 结果；随后仅调整该命令进程 PATH 到仓库配置的 Node 24.19，原样重跑得到上表正式结果。
未修改 Node、pnpm、锁文件、Verify 规则或 28 条既有例外。

新增 PostgreSQL 定向用例覆盖：新旧活动 Run 隔离、旧 submission key 重放、手动/定时同映射、正式
Connector/来源值。由于本热修未分配 Feature DB，本树没有连接任何本地、集成或生产 PostgreSQL，
这些 integration 用例留给 ca97 的 disposable PostgreSQL / CI Gate 2；不得把未执行写成通过。

## 未执行与下一负责人

- 未执行真实平台请求、生产只读验证、原生 Electron、生产数据库、迁移或部署。
- ca97：独立审查 v7/v8/v9 兼容边界，并在 disposable PostgreSQL 跑新增 integration 用例；Gate 2
  通过后合入 Green 并核对精确 CI。
- Main：按 Release Gate 发布 Backend；无需重复前端视觉验收。部署后确认实际运行 SHA、健康状态，
  并用受控最小请求验证知名 `1`、非知名 `0`，不得用 HTTP 200 代替筛选结果差异。
