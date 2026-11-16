# Worker 预检冷启动修复 Gate 1

- 基线：Green dev `dc328d70d9accd6daa201e03e0ad4152fd2ebe7b`。本交接所在提交为候选。
- 现象：精简版真实进程创建 Worker 预检任务返回 `DATABASE_OPERATION_FAILED`。冷启动时任务表保留的历史参数预设外键缺少 ORM 元数据，任务 flush 触发 `NoReferencedTableError`。
- 修复：任务及定时模型显式引用已有历史模型元数据，不注册旧路由、不恢复影刀执行、不改变数据库或迁移；数据库仍为 `20261116_0056`。
- 验证：全新进程内存数据库创建任务；独立 Feature PostgreSQL `control_center_feat_worker_only_v1` 上冷启动正式接口返回 202、重复提交复用同一任务；并发去重及合成 Worker 预检结果链通过。未请求真实平台。
- 其他检查：Backend 非集成测试 757 项通过；`git diff --check`。不包含商品库类目判断修改。
- 回滚：按正常发布流程回退此提交；原问题会重新出现。生产已有等待中的商品预检不得手动重建，发布后通过其既有自动处理路径只读核验。
