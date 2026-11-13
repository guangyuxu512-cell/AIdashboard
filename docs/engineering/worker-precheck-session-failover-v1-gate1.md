# Worker 商品预检会话失效与分配：Gate 1

- 基线：Green dev `ee3124c7cadb7fd197f44411194ecedc4909d3b4`；独立 Feature `feat/worker-precheck-session-failover-v1`。
- 范围：复用既有设备任务、RPA 本机 SQLite 会话和商品库直传队列，优先分散空闲设备及店铺；平台明确要求登录时保留旧任务并换店，Session 更新后重新参与。无效凭据不迁移；网络、签名、无权访问及风控不判作登录失效。不同设备可使用同一店铺，不设置全局店铺锁。
- 契约、版本与回滚：见 `worker-direct-precheck-result-v1.md`；Worker 0.5.4 新增可选 Session 快照标识，旧协议兼容。先中控、后商品库、再 Worker 与签名能力包；回滚先停用新能力，保留已有队列与 outbox。
- Migration：无。隔离库 `control_center_feat_worker_session_failover`、`product_workbench_test_worker_failover`；中控单一 Head `20261110_0050`。无生产数据、真实 Session 或手机参与测试。
- 验证：中控现有 PostgreSQL 定向集成文件（不运行无关的迁移降级用例）、Worker 预检/Session 桥接/直接回传/能力更新定向测试、商品库预检与结果接收测试均通过；商品库额外以隔离 PostgreSQL 和正式接收 API 验证原队列换店、回执重放及结果持久化。多设备为合成设备夹具。
- 未覆盖：抖店类目接口对真实过期会话的具体响应尚无可靠样本；合成的明确登录提示只能证明处理路径，不能证明平台一定返回该提示。已见 `10004` 的“无权访问此接口”语义不明确，不能自动判定失效。安装包及发布、真实失效换店仍需后续验收。
- 首次开发线 CI 因已有直接回传单测的模拟对象仍按旧查询顺序返回而失败，已先回退开发线；本候选同步更新该模拟并复验原回执幂等，不改变生产数据。
