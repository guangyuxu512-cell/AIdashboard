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
- 一级业务页必须复用唯一 `MobileAppShell`、品牌 Global Header 与五入口 Bottom Navigation；详情页必须复用统一 Detail Header。Page 只提供 MainContent，禁止自行创建全局 Header、返回栏或 Bottom Nav。
- Bottom Navigation 固定为“设备、任务、计划、店铺、我的”；未开发入口只能进入统一建设中页，禁止借占位实现假业务、假用户或假通知数据。
- Device Card 与 Task Card 必须共享同一套 Mobile Card 语言，包括 Surface、Radius、Border、Shadow、Padding、字阶与 Press Feedback；Feature 禁止自建独立卡片视觉体系。
- 正式 UI 优先移动端信息层级，不复制 PC Table、Drawer、Topbar 或字段表单布局。
- Apple-like 视觉只通过克制的 Surface、Radius、Spacing、Typography 与 Motion 建立，不依赖大量 Glass、Blur、Glow 或夸张 3D。
- Touch Press Feedback 是主要交互反馈；Hover 只能辅助预览，不能承载必要状态或操作。
- Global Header 固定为品牌、Theme Toggle、Notification Bell；Theme 必须在 Bell 左侧，禁止一级 Page 添加第二层巨大标题栏。
- Card 与 Icon Button 的 Press 行为优先复用全局 CSS 语义类，禁止为每个 Feature 新建 Wrapper 或 JS Pointer 动画。
- Auth、JWT、RBAC 当前未实现；只能保留 `requiresAuth`、`permission`、Guard 与 Authorization Header 插槽，禁止假登录、假 Token、假角色。
- Frontend Permission 只控制体验，不构成安全边界；真实 Authorization 必须由 Backend 执行。
- 未来 Data Scope 必须由 Backend 在 API/Query 边界过滤，禁止 Mobile 获取全量后本地过滤。
- Mobile User Authentication 与 Worker Device Token 永久分离，Mobile 禁止使用 Worker Token。
- 不复制 Desktop 页面或组件后仅修改 CSS；必须按触控、Safe Area、Sheet/Popup 与手机信息密度重新组合。
- 没有真实复用或业务需求时不建立万能抽象，也不新增 `components/`、`common/`、`helpers/`、`services/`、`libs/`。
- Foundation 的无业务数据限制仅适用于 `/__foundation`；真实业务页必须依据正式 Backend Contract 实现，且不得把测试 Fixture 或 Mock DataSource 带入生产代码。
- Device 的 `enabled`、Worker Runtime/Presence、Provider Inventory 与 Skill Capability 是独立事实；禁止合并成“设备正常”，也禁止根据心跳时间在 Mobile 重算在线状态。
- Device Center 当前只读；禁止停用、移除、绑定、运行应用、停止任务、重启 Worker 或修改任何 Capability。
- 正式 Mobile UI 禁止解释实现；新增页面 Review 必须判断 UI Copy 是否可在不影响用户操作与判断的前提下删除，可以删除就删除。

## Mobile UI 文案规则

- 正式 UI 展示用户需要知道的结果，不解释系统实现。
- 禁止在正式页面显示开发说明、Contract 说明、统计实现、API 限制或技术边界。
- 禁止使用长段解释性文案填充页面；状态文案必须简短、直接、可扫描。
- 能用状态、数字或标题表达时，不增加说明句。
- 技术信息只进入开发工具、日志、测试，或“更多信息”中的必要技术字段。
- Error UI 只展示用户可理解的安全摘要，不展示实现原因；Loading 不携带技术解释。
- Empty 不写产品设计说明，Placeholder 不解释未来架构。
- 一个状态原则上只使用一个短句或短标签表达。
- Review 必须检查 UI Copy 是否可以删除而不影响用户操作；可以删除就删除。

## 完成标准

至少通过 lint、typecheck、unit test、build，并按 `docs/04-开发验证规范.md` 验证 Mobile viewport、Safe Area、主题、触控、控制台与横向溢出。
