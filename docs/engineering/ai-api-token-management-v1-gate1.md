# 中控 AI Token 管理 Gate 1

- Feature：`feat/control-center-ai-token-management-v1`；基线 Green `9dee4b88a1ab9f3b4071f66f8af3628336cfd44f`。
- 交付独立 `/token-manager/`、管理员签发与管理接口、逐个现有管理接口的 Bearer 授权、团队范围及 OpenAPI 安全说明。没有改变 Worker Token、商品库凭据或应用间预检协议；Token 管理本身只接受超级账号人员会话。
- `0051` 新增 Token 摘要及专用管理事件表，降级仅允许已登记的空 Feature 库；共享环境回滚保留这两表。专用事件避免旧版本的既有操作日志读取器在回滚后遇到未知枚举。Feature 库为 `control_center_feat_ai_token_management`；不在本 Feature 中写 Integration 或生产。
- Feature PostgreSQL 定向验证覆盖创建、逐接口授权、团队隔离、停用/启用、撤销、过期、发放者停用、审计和迁移数据保护；任务及设备均有跨团队对照。其他团队操作沿用既有普通成员权限边界，并以目录测试检查它们经过 Team Actor；Gate 2 仍应复核必要的模块边界。
- 本地独立页面通过浏览器 Mock 检查。隔离 Feature PostgreSQL、真实 Backend 和浏览器联动完成管理员登录、创建、授权读取、拒绝写入、停用、恢复、撤销、事件读取及 OpenAPI JSON 代理；测试账号和记录已清除，无平台请求。独立端口已停止，不影响 Integration。
- Backend 非集成回归、Frontend 单元测试、类型检查、lint 和 Real 构建已执行；代理容器测试已补入现有 CI，但本机无 Docker，具体结果以 CI 为准。公网、Integration、CI、Release 和生产验收尚不能由 Feature 验证代替。
- 回滚：应用回退并保留 `0051` 两表及审计；从历史数据库备份恢复后，可能重新启用原已撤销 Token，应先复核和撤销受影响凭据。
