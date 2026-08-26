# Mobile AGENTS.md

## 定位与技术栈

Mobile 是独立的手机 Web Frontend，不是 PC Frontend 的复制版，也不承载 Backend 业务规则。

固定使用 Vue 3、TypeScript、Vite、Vue Router、Pinia、Vant、Axios、TanStack Vue Query、Vitest、Playwright、ESLint、Prettier 与根 pnpm workspace。

处理任务时依次读取：根 `AGENTS.md`、本文件、`docs/00-文档索引.md`，再按索引读取专项文档和检查现有实现。

## 硬约束

- 产品 UI 必须中文，代码命名与 Backend DTO 字段保持英文。
- API URL、DTO、状态、分页、错误码与权限码禁止猜测；Backend Pydantic/OpenAPI 是权威来源。
- 依赖方向固定为 `pages → features → entities → shared`，禁止反向依赖或跨 Feature 导入内部实现。
- Page 只做页面组合，不直接承载大量 API、复杂业务状态或基础 UI 实现。
- 全局只有一套 Mobile Design Token；禁止 Page/Feature 私建 Token 或颜色系统。
- 颜色字面量只允许出现在全局 Token 定义或明确的第三方适配文件，业务代码必须消费 Token。
- 开发 UI 时依次检查 Vant、`mobile/shared/ui`、当前 Feature；禁止页面重复手写通用控件。
- 不为 Vant 每个组件创建无价值的一行 Wrapper；只有统一语义、行为、可访问性或重复配置时才抽象。
- Backend 访问只能经 `src/shared/api/` 的唯一 Client，再由 Entity API/DataSource 消费；Page 禁止直接调用 Axios 或拼 URL。
- Mobile 不复制 Backend Guard、状态机或业务合法性判断，也不重新设计业务状态。
- Router 只在 `src/app/router/` 注册；Page 禁止动态注册 Route。
- Auth、JWT、RBAC 当前未实现；只能保留 `requiresAuth`、`permission`、Guard 与 Authorization Header 插槽，禁止假登录、假 Token、假角色。
- Frontend Permission 只控制体验，不构成安全边界；真实 Authorization 必须由 Backend 执行。
- 未来 Data Scope 必须由 Backend 在 API/Query 边界过滤，禁止 Mobile 获取全量后本地过滤。
- Mobile User Authentication 与 Worker Device Token 永久分离，Mobile 禁止使用 Worker Token。
- 不复制 Desktop 页面或组件后仅修改 CSS；必须按触控、Safe Area、Sheet/Popup 与手机信息密度重新组合。
- 没有真实复用或业务需求时不建立万能抽象，也不新增 `components/`、`common/`、`helpers/`、`services/`、`libs/`。
- 本轮不开发真实业务页面，不修改 Backend/Frontend/Electron/Worker，不运行 Migration，不操作 VPS 或真实 Worker。

## 完成标准

至少通过 lint、typecheck、unit test、build，并按 `docs/04-开发验证规范.md` 验证 Mobile viewport、Safe Area、主题、触控、控制台与横向溢出。
