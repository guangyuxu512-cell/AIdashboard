# frontend/AGENTS.md

## 1. 适用范围
约束 `frontend/` 下所有 Vue Renderer 代码。
修改前必须先读取根 `AGENTS.md`。

## 2. 固定技术栈
- Vue 3
- TypeScript
- Vite
- Vue Router
- Pinia
- Naive UI
- Axios
- TanStack Vue Query
- vee-validate
- Zod
- Apache ECharts
- dayjs
- VueUse
- Vitest
- Playwright
- ESLint
- Prettier
- pnpm

未经明确批准禁止替换。

## 3. 文档路由
先读 `frontend/docs/00-文档索引.md`。

| 任务 | 必读 |
|---|---|
| 新增页面 | 01 + 02 + 03 + 04 + 08 |
| 新增业务功能 | 01 + 02 + 05 + 08 |
| 调整 UI/字体/间距 | 03 |
| 修改页面结构/滚动/布局 | 03 + 04 |
| 接后端 API | 05 |
| 修改 Pinia / Query 状态 | 06 |
| 修改路由菜单 | 04 |
| 新增公共组件 | 01 + 03 + 08 |
| Bug 修复 | 07 + 对应专项文档 |
| 大范围前端重构 | 01 + 02 + 07 |
| 新增平台 / 平台展示 / 平台选择 | 11 |

## 4. 目录边界

```text
src/
├── app/
├── pages/
├── features/
├── entities/
├── shared/
└── stores/
```

- `app`：应用启动、Router、Layout、Provider、全局初始化。
- `pages`：路由页面，只负责编排页面级内容。
- `features`：可执行的业务动作。
- `entities`：稳定业务实体及复用展示。
- `shared`：完全通用且不依赖具体业务的能力。
- `stores`：Pinia 客户端全局状态。服务端数据默认不塞 Pinia。

## 5. 强制复用
实现任何页面前必须先搜索：
1. Naive UI。
2. `shared/components`。
3. entities 对应组件。
4. features 已有业务组件。
5. 现有页面模式。

有组件必须使用，禁止重新手写同类组件。
已有 PageHeader、PageSection、DataTable、StatusTag、EmptyState、LoadingState、ErrorState、ConfirmDialog、ShopSelector、DeviceSelector 时，不得创建第二套近似版本。

## 6. 抽象
以下必须抽象：
- 两个以上页面重复的 UI 结构。
- 相同实体重复显示逻辑。
- 重复 API 查询参数处理。
- 重复状态映射。
- 重复表格列构造逻辑。
- 重复权限判断。
- 重复格式化逻辑。

优先位置：
- 通用 → shared
- 领域 → entities
- 业务动作 → features

禁止把业务专用代码塞进 shared。

## 7. 禁止猜接口
Frontend 不得猜 URL、DTO 字段、状态枚举、权限码、分页字段、错误结构。
必须从 API Contract、现有类型、OpenAPI/生成类型或 Backend schema 确认。

## 8. 状态
- Pinia：用户、权限、主题、当前上下文等客户端状态。
- TanStack Vue Query：服务端查询、缓存、失效、刷新。
- 组件局部状态：只属于当前组件。
- Form：vee-validate + Zod。

禁止把所有 API 数据长期塞进 Pinia。

## 9. UI
- 样式必须使用 Design Token。
- 不允许页面自行定义另一套字体、间距、圆角、颜色。
- Naive UI Theme Override 优先于覆盖内部 DOM。
- 页面必须遵守统一 Sidebar / Topbar / PageHeader / PageSection。
- 页面滚动、表格高度必须遵守布局文档。
- Dialog/Modal 必须限制在 Viewport 内；动态内容只由 Overlay Body 承担主纵向滚动，Header/Footer 固定，禁止依赖页面主滚动容纳超出视口的弹层内容。
- Business Skill 参数只能消费 Backend Skill Catalog 的正式 Schema；Frontend 不得按 Skill ID 猜字段，也不得为 Scheduler 手写第二份参数定义。

## 10. 第三方库
已有库能解决的问题禁止重复造轮子。
新增同类库前必须确认现有能力无法合理满足。
禁止同时引入多套 UI、Chart、Date、Form 库。

## 11. 验证
按改动范围执行：
- lint
- typecheck
- unit test
- build
- 关键交互必要时 Playwright
