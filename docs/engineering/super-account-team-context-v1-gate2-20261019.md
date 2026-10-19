# 超级账号业务团队上下文热修 Gate 2

## 结论

- Candidate：`f06bc6254d28cd8b443942323dac9684ef2be924`。
- 本地 Integration no-ff merge：`2fc0c9721157cfb091fbbe484ff72975f3375805`。
- 独立 Review：ACCEPT。无 Team 的超级账号保持全局只读；选择具体 Team（包括默认团队）后，共用 Team-owned 业务资源按所选 Team 读取和写入，消除了列表可见但关联写入找不到同组资源的范围不一致。
- 保留超级账号对公司公共店铺、设备、人员和授权的全局管理能力，以及既有选品资源例外；普通成员权限不扩大。
- 无 API、DTO、错误码、Schema、Migration、依赖或 Electron 变化。

## 独立证据

- Owner 工作树精确 Candidate 且干净；merge-base、候选包含关系及 `git diff --check` 通过。
- Backend 定向：9 passed；Backend 默认全量：1076 passed，仅既有 Starlette/httpx 弃用 warning。
- Frontend 定向：5 files / 27 passed；Frontend 全量：170 files / 946 passed；Real production build 通过。
- 独立 Feature PostgreSQL：7 passed。覆盖无 Team 全局读取、具体 Team SQL 范围、同组上传关联、跨组拒绝、普通成员伪造 Team 拒绝及参数预设边界。
- Integration 运行链路：`5180 -> 8100 -> control_center_integration`，数据库单一 Head `20261017_0047`，运行代码包含 Candidate，并保持唯一开发 Electron/Profile。
- 原生人工验收：超级账号菜单能从“全部团队”切换至 `G2-SA-V1 Team A`；Team A 下 AI 写入操作可用；切回“全部团队”后只读提示、写入禁用及弹窗/选择态清理均符合预期。原生截图接口不可可靠捕获，本记录不以网页截图替代原生证据。
- Gate 2 未请求平台、Provider 或付费能力，未写 Main/生产数据库，未启动第二个 Electron。

## 发布边界

- Gate 2：PASS。以本记录提交后的精确 `dev` SHA 运行 CI；全部 Green 后再交 Main Release Gate。
- 发布无需 Migration 或 Electron 安装包。回退保留数据库、业务历史和文件，仅恢复旧菜单及读写范围问题。
