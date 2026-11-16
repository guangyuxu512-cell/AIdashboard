# Windows 执行层精简：0052 阶段 Gate 1

- 分支：`feat/windows-execution-slim-consolidated-v1`；以本文所属提交为待审候选。代码基于 Green dev `83e459a8ea5c4e1c9b7f646492cd9a7e72bfa3ef`，包含此前 `522cbe02b84cefcf2f1b0e93e9c9de4186a8de8f` 的 Worker 状态实现。
- 本阶段移除中控 AI 工作台、AI 模型、中控自有商品库和手机采集页面及路由；保留资产、任务、设备、权限、Token、独立商品库 Worker 预检、选品底座和历史事实。经营与选品执行开关在生产已暂停；现有售后定时保留。
- Migration 唯一 active Slot 为 `20261114_0052`，down revision `20261113_0051`。该迁移删除 AI 私有表，保留资产与通用任务；已在专用 `control_center_feat_windows_execution_slim` 验证。回滚依赖升级前经过可读性验证的备份和兼容代码，不以重建空表代替恢复。
- 本阶段不含 `20261116_0053`。用户已确认旧中控商品库数据和采集任务不再需要；0053 在 0052 通过 Gate 2、dev CI 和 Slot 释放后实现，不修改独立商品库、NAS 或手机。经营商品指标历史保留，旧服务器采集入口还需在后续阶段移除。**本阶段不得单独发布生产。**
- 基于代码提交 `522cbe02` 的 backend/frontend/worker 完整离线校验、Feature PostgreSQL 的 Worker 状态/失效/并发检查、前端类型及 lint 检查通过；本提交仅变更交接文档。与 `bbebac78` 相比没有 Electron 改动，复用该版本已通过的 Electron 离线检查。平台实测仅包括 HuanYu 只读商家身份接口，返回成功且身份匹配；不能推断全部店铺或类目可用。
- Worker 0.5.6 为未安装的本地测试包；签名公钥与 0.5.5 一致，版本与信任锚自检通过，未做真实设备部署或 Integration 原生窗口验收。新状态上报不传 Session；既有类目预检仍将 Cookie 临时传给受限服务器签名接口，再由 Worker 本机请求平台。
- Integration 仅允许连接 `control_center_integration`，使用现有 8100/5180，相关后台采集开关关闭。集成备份须经可读性验证；旧任务、选品计划、设备和 Session 不得因验收而清除。Gate 2 需核验已删路由、资产、Worker 心跳/领取/结果、店铺状态、定时和选品暂停边界。
