# Worker 本机店铺与纯 Web：Gate 1 交接

- 基线：Green dev `b5465980c393a735bd973b9ed381697a886898a3`，GitHub CI `43857260042` 成功。候选在 `feat/worker-only-shop-context-v1`，实现和失联旧任务保护提交分别为 `0731e2409a65096943bc02a7dac6fb4f8e963d91`、`edeb3ed69403bafd1ffe2a0fa9aa9081d322f065`；以本交接所在分支 HEAD 为最终候选。
- 范围：删除中控 Electron、旧店铺登录及 Session 管理、影刀执行与绑定；设备使用 Worker 上报的本机店铺映射。经营历史只读，选品底座保留并暂停，所有既有定时执行暂停；资产、任务事件、认证、API Token、Worker 和独立商品库预检保留。原 AI 工作台与旧中控商品库此前已合入，不重复迁移。
- 契约：Worker 从 RPA 本机读取 Session 并直接回传商品库；中控继续调度。兼容现有 0.5.5 设备，预检每设备最多 5 家店、每店最多 3 个任务；已有 0.5.5 配置和旧 IP 不强制改写。`application_shop_session_clients_file` 仅保留作独立商品库应用授权配置路径兼容，不保存店铺 Session。
- Migration：唯一 `20261116_0056`，down `20261116_0055`；Feature 数据库为 `control_center_feat_worker_only_v1` 和 `control_center_feat_worker_only_v2`。删除的表、历史保留及不可逆回滚方式见 Migration 登记。
- 验证：Feature 后端非集成测试和相关任务、映射、预检测试通过；前端 104 个测试文件、515 项及类型检查和 Real build 通过；Worker 全量 167 项通过；隔离 PostgreSQL 的本机映射、旧版本兼容、预检回传与并发、0056 失联旧任务保护通过。Worker 0.5.7 安装包完成离线自检，未在生产设备安装。
- 风险与限制：生产发布前需校验真实在线 Worker、商品库预检连接、旧任务状态、可读备份及迁移保护；本候选不修独立商品库的聚水潭来源类目识别问题。0056 不支持直接降级，依赖经过验证的备份与兼容版本回滚。