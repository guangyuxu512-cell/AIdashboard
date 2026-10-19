# AI Asset Upload Access V1 Gate 2（2026-10-19）

## 结论

- Candidate：`8420716bf199e653497e5cfc32b68c19365e27b3`。
- 基线：精确 Green `59894d98d88eff3529fb9d6b4cfecd45694d2156`。
- Review 结论：ACCEPT。AI 工作台上传、读取、缩略图、清理、素材关联、生成提交及重试使用同一 AI 文件资格边界；通用素材库权限未被扩大。
- 本候选包含已审查的图片比例/预览候选 `87ad1e03...`，无 Schema、Migration、依赖或 Electron 壳变化。

## 独立验证

- 精确候选 `git diff --check` 通过；Owner 工作树与 Integration 工作树检查时均干净。
- PR `#17` 的精确候选 CI run `39148354013` 四项均为 SUCCESS，包含真实双层 Nginx 上传代理回归。
- Backend 定向单元测试：23 passed。
- Frontend 定向测试：4 files / 32 tests passed；使用项目要求的 Node 24，首次 Node 20 启动失败明确归为本机运行时不匹配，未计作候选失败或通过。
- Dedicated Feature PostgreSQL：5 passed。首次执行停在连接阶段，查明为已登记的 `127.0.0.1:35433` 受信任隧道未监听；严格主机校验恢复原隧道后同一组测试全部通过，未修改数据库凭据、权限、HBA 或业务代码。
- Real production frontend build/typecheck 通过。
- Playwright Real API/生产 bundle 专项：15 passed，覆盖上传单次发送、部分失败、HTML 413、诊断信息、四类图片比例、慢图/切换、详情失败重试及小窗口缩放。
- 用户在唯一开发 Electron 中确认当前页面已显示；该记录仅作为可见结果，不虚构为未执行的额外人工操作。

## 运行与数据边界

- Integration runtime 使用 `5180 -> 8100 -> control_center_integration`，唯一既有 Electron/Profile 保留；Backend 与 Frontend 均从精确候选工作树启动。
- 真实 PostgreSQL 测试只写专用库 `control_center_feat_ai_asset_upload_access` 的稳定范围夹具并清理；未写 Main/生产库，未请求 Provider。
- 本次没有新 Migration Slot；当前 Schema Head 继续为 `20261017_0047`。
- 临时本机脚本和敏感值未提交；连接信息只在受保护配置中读取，未输出凭据。

## 发布交接

- Gate 2 技术结论：PASS，可正常 `--no-ff` 合入 `dev`。
- 合入后必须以精确 merge SHA 的 CI Green 为准；Main Release Gate、生产部署和生产健康核验仍由 Main 按既有流程执行。
