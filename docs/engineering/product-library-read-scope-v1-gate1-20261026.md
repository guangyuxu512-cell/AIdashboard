# 商品库全部团队读取修复

## 基线与范围

Feature Owner 为 81a1，下一责任人为 ca97。分支
`hotfix/product-library-read-scope-v1` 从 `origin/dev`
`0410ec7a65cc1d9d9a7d9ad196945bea9fee9bb5` 创建；Candidate 完整 SHA 见正式 Handoff。

本候选只修“商品中心 → 商品库”的分组、列表、总数、搜索、分组筛选和详情读取范围，
以及前端团队切换时的旧状态与旧请求隔离。既有商品编辑、导入、移动、删除、重新采集等写能力
不扩展；无 Migration，不创建采集任务，不修改商品归属，不操作生产、NAS 或手机。

## 读取与写入边界

| 身份与范围 | 分组、列表、总数、搜索/筛选 | 详情 |
|---|---|---|
| 超级账号，全部团队 | `DataScopePolicy` 跨团队读取 | 可打开已授权商品 |
| 超级账号，具体团队 | 只读所选团队 | 其他团队返回 404 |
| 普通成员 | 只读成员当前团队 | 其他团队返回 404 |

分组和商品查询统一在过滤、计数、分页及按 ID 读取之前套用 `DataScopePolicy`。详情先按同一策略
授权商品，再用该商品真实 `team_id` 读取版本和最新采集状态，保留现有单商品 UU 导出。
写路径继续调用原 `_write_team`，全部团队不会获得编辑、导入或其他写权限。

前端切换 Actor/Team 时同步清空旧列表、详情、勾选、旧分组筛选、弹窗及 UU 导出忙碌态；
分组、列表、详情、导出分别使用范围代次和请求代次，旧响应不能覆盖新范围或触发旧文件下载。

## Gate 1 实际验证

| 检查 | 结果 |
|---|---|
| Backend 商品采集/商品库定向 | 187 PASS；含商品库 SQL 范围、详情真实 team、API 兼容回归 |
| Feature PostgreSQL 正式 API | 19 PASS；真实 SQL 覆盖全部团队、具体团队、成员、分页/total、搜索、分组和详情 |
| Frontend 商品库/采集域定向 | 7 文件、27 PASS；含全部团队无 Team、切团队清状态、列表/详情/UU 导出旧响应隔离 |
| Frontend 全量 | 177 文件、981 PASS |
| Frontend lint / typecheck | 均 exit 0 |
| Frontend Real 生产构建 | exit 0；隔离输出 `.dev-runtime/product-library-read-scope-v1/build-real` |
| 格式和差异检查 | Prettier、ESLint、`git diff --check` 均通过 |

PostgreSQL 测试复用分配给 Feature 的
`control_center_feat_mobile_product_collection_integration`，测试数据位于外层回滚事务；
Migration Head、消费者开关和生产数据均未改。仅有既有 Starlette/httpx 弃用提示和 Vite 大 chunk 警告。

## Gate 2 与发布交接

ca97 应对精确 Candidate 做独立 Gate 2，重点验证商品中心商品库：超级管理员“全部团队”可浏览
分组、商品和详情，搜索/分组/总数正确；切到具体团队后旧详情、勾选和不适用分组消失且范围收窄；
成员隔离和既有 UU 导出保持。采集任务页只做回归，不能替代商品库验收。

Gate 2 不新建采集任务，不迁移或修改商品归属，不操作 NAS、手机或生产数据。通过后再走 dev GitHub CI、
Main Owner 合并及 main CI、本地 CD 与生产商品库截图验收。回滚采用正常 revert 本候选；无数据库回滚步骤。
