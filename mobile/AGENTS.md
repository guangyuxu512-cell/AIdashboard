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
- Foundation 的无业务数据限制仅适用于 `/__foundation`；真实业务页必须依据正式 Backend Contract 实现。稳定视觉验收数据只能经 Development Only Entity DataSource 注入，Production 不得启用或自动回退 Mock。
- Device 的 `enabled`、Worker Runtime/Presence、Provider Inventory 与 Skill Capability 是独立事实；禁止合并成“设备正常”，也禁止根据心跳时间在 Mobile 重算在线状态。
- Device Center 当前不执行写操作；详情必须在 Capability 标题与能力行保留刷新、配置、运行入口，但未接入 Backend 正式 Contract 前禁止发请求或伪造成功。
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

## Mobile Layout

- 一级列表页面必须使用统一 Mobile List Page Pattern。
- Global Header、Summary、List Toolbar、Bottom Navigation 不得随业务 Card 列表滚动。
- 列表页面只有业务 List/Grid 区域作为主滚动容器。
- List Toolbar 统一承担标题、数量、主选择器和筛选。
- 状态选择与筛选不得无必要占两行。
- 页面不得自定义 Header、Toolbar 或 Bottom Navigation 高度。
- Page Horizontal Padding、Section Gap、Card Gap 必须使用统一 Layout Token。
- Device、Task、Shop、Schedule 等列表卡必须控制文字行数，避免内容撑高。
- Card 稳定通过结构、Padding 和行数实现，不通过随意固定死高度。
- 新列表页面优先复用 `MobileSummaryStrip` 和 `MobileListToolbar`。
- 不得复制 PC 列表或表格布局到 Mobile。

## Stable Mobile Layout Components

- Mobile 一级列表页面使用统一 List Page Pattern。
- Header、Summary、List Toolbar、Bottom Navigation 不随业务列表滚动。
- 正式移动端滚动容器默认隐藏可见 Scrollbar，但必须保留触控、滚轮、触控板与键盘滚动。
- 工具行禁止套独立大 Card。
- Selector/Filter 的视觉尺寸与 Touch Target 分离。
- Summary 是信息容器，不设计成大按钮。
- Device/Task 卡通过结构和行数保持稳定高度。
- Device Detail 必须通过 Capability Panel 固定刷新入口，以及逐 Application/Business Skill 的配置与运行入口。
- Device 业务动作必须复用 Backend 正式 Contract，不建立 Mobile 专属第二套业务链。
- 尚未接业务 Contract 的操作不得 Fake Success。
- 新业务页面不得自行定义 Page Padding、Toolbar Height、Summary Height 或 Bottom Navigation Height。

## Device Detail Interaction

- 点击 Device Card 必须进入 Device Detail，禁止默认进入 Task Detail。
- 只有明确点击 Device Detail 的 Current Task 时才进入 Task Detail。
- Device 与 Yingdao Runtime 摘要采用统一双列 Summary Pattern。
- 正常产品 UI 优先显示 Application/Skill Name，不显示 UUID。
- Capability 区域固定最大高度，超出内容内部滚动或进入查看全部页。
- Application/Skill 每行使用稳定的 Name + Actions 结构。
- Application 参数属于 Application 执行上下文，不做 Device 级全局参数按钮。
- Run / Configure 必须复用正式 Backend 业务 Contract。
- Internal Skill 默认不得作为普通用户核心操作能力展示。
- 正式 Mobile 滚动容器默认隐藏 Scrollbar，同时保留触控、滚轮、触控板与键盘滚动。

## Mobile Typography & Capability

- Mobile 字体必须使用统一 Typography Scale，业务页面不得自由定义字号或字重体系。
- Capability 类型选择使用紧凑 Segmented Pattern，不使用 PC/Web 式 Underline Tabs。
- Count 属于辅助信息，不与 Tab Label 争夺视觉权重。
- Section Refresh 属于轻量 Icon Action，不使用大文字 Button。
- Capability 默认显示 5 行，第 6 行后内部滚动。
- Capability 行保持 `Name + Actions` 稳定结构。
- 视觉按钮尺寸与 Touch Target 必须分离。
- 普通详情页面继续保留全局 Bottom Navigation。
- 只有沉浸式工作流允许隐藏 Bottom Navigation。

## Mobile UI 迭代与冻结规则

- Mobile UI 必须按顺序推进：1) Layout / Component Structure；2) Dimensions / Spacing / Typography；3) Color / Surface / Radius / Shadow / Theme；4) Interaction / Press / Motion / Touch；5) Loading / Empty / Error / Toast / Dialog；6) Business Interaction Contract。
- Stage 1 未经人工验收，不得提前开展跨组件的尺寸微调、配色、质感或动效润色。
- 核心 UI 一次只定型一个组件；自动验证通过且人工确认后，才允许在 Design System 标记为 `Frozen`。
- `Frozen` 组件的 Layout、Anatomy、Height、Padding、Typography Role 与 Interaction Contract，
  未经用户明确要求不得随意修改；发现问题时先报告，不得顺手重构。
- 新页面必须优先复用已冻结 Pattern、Shared UI、全局 Token 与 Vant，不得在 Page/Feature 自建
  Typography、Spacing、Color、Radius、Shadow、Press 或 Motion 体系。
- 自动测试只证明约束与回归，不等同于视觉验收；只有经人工确认的核心组件才能进入 `Frozen`。
- 视觉尺寸与 Touch Target 是独立职责；不得为了 44px 命中区把视觉控件画成巨大按钮。
- 正式产品 UI 禁止用业务页面魔法数修补全局 Header、Shell、导航或滚动布局。

## Visual Development

- Mobile 视觉开发不得依赖真实 Backend 是否在线；需要稳定视觉数据时使用 Development Only Mock DataSource。
- 禁止在 Page 硬编码 Mock 数据，Mock 与 Real 必须共用同一 Entity、Query、Mapper、Feature、Page 与 UI。
- 禁止 Production API 失败后自动 Fallback Mock；真实空数据仍展示正式 Empty，真实失败仍进入正式 Error。
- Production UI 禁止展示 Mock 实现说明；开发模式只允许通过 Console 等非产品界面确认数据源。
- 人工视觉验收优先使用稳定 Mock Fixture；Real API Contract、Loading、Error 与 Refresh 属于独立验收阶段。

## 完成标准

至少通过 lint、typecheck、unit test、build，并按 `docs/04-开发验证规范.md` 验证 Mobile viewport、Safe Area、主题、触控、控制台与横向溢出。
