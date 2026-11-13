# 中控 AI Token 管理 Gate 2

- 原候选 `acde515e62048456d980fdc4dbbfff38fd22f32f`，从 Green `9dee4b88a1ab9f3b4071f66f8af3628336cfd44f` 开发；候选 PR CI `43469016697` 的 Backend、Frontend、Windows 和 Container 均成功。
- Integration `control_center_integration` 先生成受保护备份（918788 字节，SHA-256 `506e054f0b388ce6f9e00d8e3bab9e2b57d1e25b1133b38c594926012214dee7`，494 项恢复目录可读），再由精确候选正常升级 `20261110_0050 → 20261113_0051`；既有用户、团队、店铺、设备、任务、定时和店铺会话数量保持。
- 在 `5180 → 8100 → control_center_integration` 使用已有集成超级账号正式登录，真实浏览器与正式 API 完成 Token 创建、按接口授权、无权写入拒绝、停用、恢复、撤销及管理记录；测试 Token 与记录已按唯一名称清理。测试进程关闭后台执行循环，不请求平台。
- 使用 Integration 已有两个团队与任务事实核对限定团队总数及全局总数；其他团队和缺少团队头均被拒绝，未授权写入被拒绝，撤销立即生效。普通成员无管理权限使用合成身份进行授权分支检查，不冒称取得该成员真实登录。Feature 库另对两团队任务及设备隔离、停用发放者、过期、撤销、迁移保护完成真实 PostgreSQL 验证。
- OpenAPI 通过集成页面同源代理返回 JSON 并声明 Bearer；生产 Nginx 独立页面与 OpenAPI 转发由候选 Container CI 验证。现有 Worker、应用间和手机协议继续使用原有独立凭据，不列为 AI 管理 Token 的权限。
- 本记录仅为集成验收。无生产写入、平台请求或客户端包改动；本次合并后的精确 dev CI、Release Gate、main CI、生产部署和生产验收仍须分别通过。`0051` 在该精确 dev CI 成功前保持 active，成功后可按既有流程释放。
