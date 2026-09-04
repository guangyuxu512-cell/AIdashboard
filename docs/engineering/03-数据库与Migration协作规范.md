# 数据库与 Migration 协作规范

## 1. 基本原则

PostgreSQL 结构演进只能通过 SQLAlchemy Model 与 Alembic Migration 完成，禁止手改任意正式环境的表结构。业务 Feature 对其 Migration 的设计、实现、测试、文档和回滚负责；Integrator 负责 Slot 协调、Gate 2 验证和拒绝不合格候选，不代替 Feature 编写新的数据库变更。

数据库按角色严格隔离：Feature 使用可重建的临时/Feature DB，Integration 只使用 `control_center_integration`，Main smoke 只使用 `control_center_dev`，未来生产必须独立。连接串、密码、密钥和数据导出不得提交。

Feature DB 的生命周期由 Integrator 负责：仅 Integrator 可通过数据库管理员身份创建和删除 Feature DB，并在工程登记表中记录实际分配。Feature Agent 不拥有 `CREATEDB` 权限，且不得自行创建、删除或改用 `control_center_dev`、`control_center_integration`；Feature Worktree 只能使用本地忽略的连接配置访问其已分配的 Feature DB。

分配顺序固定为：Feature 提出需求，Integrator 确认登记与 Migration Slot，数据库管理员创建空 Feature DB 并将 Owner 指向既有最小权限应用角色，Feature Worktree 配置本地忽略的连接后执行 `alembic upgrade head`，才可开始数据库开发。Feature 进入 Green `dev` 后，如该库已无保留价值，仍由 Integrator 删除；不得由 Feature Agent 处理回收。

## 2. Migration Slot

同一时刻只有一个活跃的 Migration Slot。需要结构变更的 Feature 在开始前向 Integrator 申请并登记：

| 字段 | 必填内容 |
|---|---|
| Feature / Owner | 分支与负责人 |
| Slot 状态 | `reserved`、`active`、`released` 或 `rejected` |
| 变更摘要 | 实体、字段、关系、索引和兼容性影响 |
| 依赖 | 需要先合入的 Migration 或无 |
| Migration 标识 | Alembic revision / 计划名称 |
| 验证与回滚 | `upgrade`、必要的 `downgrade`、数据保留与回滚说明 |

- Integrator 只分配、调整和释放 Slot；Feature Owner 才能写对应 Migration。
- 未取得 Slot 的 Feature 不得新增或重排 Migration，也不得借用无关 Migration 偷带结构变更。
- 没有结构变化的 Feature 在 Handoff 中显式写“Migration Slot：无”。
- 发生冲突、升级失败、非预期数据影响或验证不充分时，Slot 状态改为 `rejected`，候选退回原 Feature 修复；不得在 `dev` 上直接修补候选。

当前没有活跃 Migration Slot（FREE）。

最近释放记录：

| Feature / Owner | Slot 状态 | 变更摘要 | 依赖 | Migration 标识 | 验证与回滚 |
|---|---|---|---|---|---|
| `feat/ai-generation-execution-v1` | `released` | AI Generation Execution V1 已合入 Green `dev` | `20260903_0026_ai_workbench_backend_foundation_v1` | `20260903_0027_ai_generation_execution_v1` | Gate 2 已在 `control_center_integration` 验证 `0026 → 0027 → 0026 → 0027`；`control_center_feat_ai_generation` 已由 Integrator 回收 |
| `feat/ai-backend-foundation-v1` | `released` | AI Workbench Backend Foundation V1 已合入 Green `dev` | `20260902_0025_access_management_v1` | `20260903_0026_ai_workbench_backend_foundation_v1` | Gate 2 已在 `control_center_integration` 验证并升级至 `20260903_0026`；空的 `control_center_feat_ai_backend` 已由 Integrator 回收 |
| `feat/access-management-v1` | `released` | Access Management V1 已合入 Green `dev` | `20260901_0024` | `20260902_0025_access_management_v1` | Gate 2 已在 `control_center_integration` 验证并升级至 `20260902_0025`；空的 `control_center_feat_access` 已由 Integrator 回收 |

## 3. Feature Gate 1

Feature Owner 在自己的可重建数据库中完成：

1. 确认变更是属性、实体还是关系，并遵守稳定 ID、约束与索引规则；
2. 编写 Model、Alembic Migration、相应 Repository/Service/Contract 与必要文档；
3. 从干净基线执行 `alembic upgrade head`，验证真实业务读写；
4. 需要降级闭环时，在可重建环境执行 `head → previous → head`，并检查应保留的数据；
5. 在 Handoff 中附上 revision、Slot、数据库角色、命令、结果、影响和回滚方式。

不得以 SQLite 代替 PostgreSQL 报告 Migration 通过，不得在测试后保留无法解释的临时表或数据。

## 4. Integration Gate 2

Integration 只在 `control_center_integration` 验证候选。Integrator 至少检查：

- Slot 已登记且 Migration 序列与当前 Green `dev` 兼容；
- `alembic upgrade head`、关键接口/服务验证和对应自动测试通过；
- 如 Handoff 声明可降级，则在可重建的 Integration 数据库按声明验证；
- 没有把环境文件、数据导出、密码、临时脚本、日志或 artifact 带入 Git；
- 合并后再次运行必要验证，确认 `dev` 保持 Green。

候选失败时先拒绝并保留证据。已合入共享 `dev` 后出现破坏性失败，使用可审查的 `git revert` 回退合并；数据库处理必须根据该 Migration 的明确回滚方案进行，禁止用 Git `reset` 或手改生产/共享数据库掩盖问题。

## 5. Main smoke 与发布

`control_center_dev` 只服务 Main smoke，不是 Feature 或 Integration 的公共试验库。Release Gate 必须确认 Green `dev` 的 Migration 序列、部署顺序、兼容性和回滚说明；生产执行由独立发布流程授权，本规范不授权将开发 Migration 直接用于生产。
