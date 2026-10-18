# 选品品牌映射热修 V1 Gate 2

## 结论与范围

- 最终 Feature Candidate：`4429dddad481a07e0452d2870c15a64d9c759b20`；Green 基线：
  `a6df9ac43b0987b68bd13313ab40d2aeca84c63d`。
- ca97 已完成独立审查和 Gate 2，按 `--no-ff` 合入 dev；业务合并提交为
  `f012eab05d3a9fb631c201450fa8a4968070c9aa`，第二父提交精确等于最终 Candidate。
- 本次只修正新请求的品牌映射：不限 `-1`、知名品牌 `1`、非知名品牌 `0`。新非默认品牌请求
  使用 v9；历史 v7/v8 继续按当时实际发送的 `known=0`、`unknown=1` 读取和重放。
- 无前端、Schema、Migration、依赖或运行配置变化；不混入商品数据 0047、定时 B 或其它功能，
  无需重复 Electron 视觉验收。

## 独立审查与测试

| 检查 | 结果 |
| --- | --- |
| 差异及版本边界 | v9 已贯通冻结、执行、策略关联、来源写入；历史 v7/v8 投影保持旧映射；旧 activity/submission 不会被新映射错误复用 |
| 重试边界 | 621 业务探查仍仅限既有默认品牌版本；v9 非默认品牌没有扩展通用重试或回退 |
| 最终 Candidate 非 PostgreSQL 选品测试 | 295 passed、961 deselected；仅既有 Starlette/httpx warning |
| 最终 Candidate 隔离 PostgreSQL | 43 passed；覆盖品牌、计划和目标页三份 integration 用例 |
| 代码范围 | `git diff --check` 通过；无前端、Migration、锁文件、依赖或配置变化 |

PostgreSQL 正式结果来自隔离 Feature 数据库 `control_center_feat_product_selection`，单一 Head 0046，
应用角色为最小权限 `control_center_dev_user`。执行前后策略、Run、候选、来源、结果项和计划表均为 0，
ShopSession 为 0，没有真实平台请求；既有两个旧测试前缀在执行前后数量不变，本轮没有留下业务数据或
测试夹具。

## Integration 兼容与审计边界

ca97 对 `control_center_integration` 做了只读兼容预检：数据库保持单一 0047；Candidate Reader 成功
解析三条真实历史冻结请求（v7 两条、v8 一条）。三条记录的稳定摘要在检查前后均为
`a3d973cb1e27617df0f8505da7fa018d5917407249586216fde3e6acf3e94ed5`，没有改写历史 JSON、事实或
审计记录；本轮测试前缀残留为 0。

首次 PostgreSQL 尝试误用了存在既有到点计划的 Integration 数据库，因此全局计划领取命中了已有
`G2 Selection-B` 记录，而不是本轮夹具。审计记录保留如下：Run
`27631203-4763-4ad0-a067-2e69599d3c0e`、策略
`e54dc332-0677-4827-be37-f626c520b6b8`、HuanYu、v4；在 Session 阶段以
`AUTH_INVALID` 结束，保存/补充均为 0，未发出平台请求。该记录未删除或伪造修复；随后所有正式
PostgreSQL Gate 均切换到隔离 Feature 数据库执行。

当前唯一开发 Electron、5180/8100 和商品数据 0047 预览未因本热修重启、降级或换库；本次 Gate 2
不以当前预览冒充品牌热修运行证据。

## 发布与回滚约束

本记录随 dev prospective Green 提交。只有该精确提交的 CI 全部成功后才可标记 Green，并交 Main
执行 Release Gate、main CI 和正式部署。生产发布只更新 Backend 代码，不执行 Migration，不修改
现有采集计划、Session、历史事实或配置。

生产出现 v9 Run 后，不得回退到不认识 v9 的旧 Backend，也不得改写/删除 v9 或历史 v7/v8 数据。
需要止损时应使用既有执行开关暂停新任务，同时保留兼容 Reader 和全部审计数据。

发布后只允许一次最小、受控、只读品牌对照：使用已有合法 Session 和同一筛选条件，分别验证最终
Query 为知名 `1`、非知名 `0`，并比较实际结果集合；HTTP 200 或签名成功不能单独作为筛选生效证据。
不得创建正式 Run、写候选池、更新 Session 或扩大为全榜重采；认证、风控或限流时立即停止并如实报告。
