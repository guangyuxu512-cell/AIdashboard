# Worker 定时恢复

- 基线：Green dev `e12d1cd63b1aba9be4928cea65e099452c6b8efe`。无 Migration；数据库 Head 为 `20261116_0056`。
- 将 Worker 定时恢复为显式开关控制，默认仍关闭；复用现有扫描器、任务队列和设备店铺映射。
- 到期查询排除旧影刀技能及带旧影刀参数预设的计划；选品、经营采集仍被各自原有关闭规则约束。
- 计划列表返回执行器实际状态，前端仅在关闭时提示。不会修改、启用或补执行旧计划。
- Feature DB：`control_center_feat_worker_schedule_resume_v1`。定向测试覆盖真实分钟到点、Worker 领取、重复扫描、停用及影刀计划隔离、选品关闭，另运行既有商品库预检和并发回归。
- 发布前复核生产旧计划均处于停用且无执行中的预检任务；部署启用 `BACKEND_WORKER_SCHEDULE_EXECUTION_ENABLED`，其余功能开关不变。回滚关闭该开关并重建 Backend，不修改旧计划或任务数据。
