# 选品库前端与 Mock 交互 V1

状态：UI_ONLY；前端契约草案，不是 Backend DTO 或平台接口契约。
Green 基线：`b34e43cb90356e03d2f793c4146c6775a11f5ab3`（ca97 确认精确 CI PASS）。
分支：`feat/product-selection-frontend-v1`。无 Backend、数据库、Migration、Electron 壳、真实平台或调度变更。

## 实施前复用清单

| 现有路径（frontend/src） | 用途 | 新增边界 |
| --- | --- | --- |
| shared/components/ContextSwitchBar.vue | 保留 framed 三选项和 query 历史 | 不改公共切换组件 |
| shared/components/ManagementListSection.vue、FilterBar.vue、DataTable.vue、PaginationBar.vue | 两种列表、稳定底部分页、固定列、居中 | 仅增加选品业务列定义 |
| shared/components/DetailDrawer.vue | 商品详情 | 仅新增选品指标内容 |
| shared/ui/AppDrawer.vue、AppButton.vue、AppSelect.vue、AppInput.vue、AppNumberInput.vue、AppSwitch.vue | 策略右抽屉、条件与独立保存/立即获取 | 组合已有 footer，不改变 FormDrawer |
| entities/shop/ui/ShopSelector.vue | 请求店铺 | 不建立第二套店铺选择 |
| shared/styles/tokens.css、app/providers/naive-theme.ts | 四主题/字体/密度 | 不新增 token 或单页配色 |
| shared/composables/useAutoSearch.ts、TanStack Query | 显式列表搜索与请求隔离 | 不建立新缓存/搜索框架 |
| entities/asset/ui/AssetPreviewDialog.vue（核对但不直接复用认证取图） | 现有放大预览交互参考 | 外部商品图组合 Naive NImage，原资产链路不变，禁止使用认证 HTTP Client |

仓库无 NCascader 封装。选品 Feature 内 CategorySelector 只薄封装现有 Naive 多列级联，各父节点增加明确的“全部”选项（ID 后缀 `/*`），不创建基础控件框架。
新增领域类型、service、Mock handlers 与业务组件，是因为当前只有占位，没有选品契约/业务内容。路由与模块授权继续原注册，不增加权限码。

## 数据与能力边界

契约权威为 `features/product-selection/model/contracts.ts`，集中约定字符串 ID、nullable 指标、原始区间、页码、排序、条件及演示回执。不定义猜测的 HTTP URL。
Mock service 仅在构建环境明确 `VITE_API_MODE=mock` 且调用模式为 mock 时加载；读写只在内存，刷新恢复夹具，账号/团队变化重新隔离，三个切换项之间保持本次内存数据。Real service 不加载 Mock，不发任何选品网络请求，明确返回未接入能力。
达人账号只有演示选项，无真实登录。工具栏登录入口报告未接入，不开假页面。立即获取只返回该店演示夹具数量，并更新已保存策略的演示最近结果；不声称模拟了平台完整条件匹配，百应不编造结果。定时配置只保存演示规则，不启动后台任务。
商品外部图通过浏览器图片加载/Naive 预览，不使用系统 axios、认证 Header 或 X-Team-ID。缺失与失败单独展示并可重试。

## 请求草案

- categories(shopId)：行业/层级树；允许父级全部，选项 ID 保持字符串。
- list/save strategies：命名策略、请求店铺、共用达人、渠道、条件、可选 hourly/daily schedule。
- retrieve(input, strategyId?)：允许未保存策略；短视频返回演示回执，传入已有策略 ID 时更新其演示最近结果，百应明确不可用；不是平台采集成功。
- list/get candidates：先完整筛选，再原始日期/差评率排序（null 双向末尾、同值 ID 稳定），再分页。
- demo action：屏蔽/恢复仅修改 Mock 池；采集入库仅演示回执，不写正式商品库。
- 未确定的“更多”日期选项、原始支付金额单位不猜测、不换算。

Real 后续接入须先冻结 Backend/OpenAPI 与授权、达人 Session、平台 Endpoint、单位和调度契约；不能直接把本草案 URL 化。

## Gate 1 验证与交接边界（2026-10-08）

执行位置为 81a1，浏览器地址 `http://127.0.0.1:4176`，Vite `--strictPort`。未启动 Backend、数据库或 Electron，不占用 Integration 5180/8100。

| 命令（frontend 目录） | 实际结果 |
| --- | --- |
| `pnpm lint` | PASS |
| `pnpm build`（含 `pnpm run typecheck`，强制 Real production build） | PASS；无 selection-mock-handlers 构建 chunk。既有大 bundle 提示仍存在，未扩大到性能重构 |
| `pnpm test` | 130 个文件、531 项 PASS；既有 jsdom XHR AggregateError stderr 未造成失败，不把它记为零告警 |
| `pnpm exec vitest run src/features/product-selection src/shared/components/DataTable.spec.ts` | 3 个文件、16 项 PASS |
| `PLAYWRIGHT_FRONTEND_PORT=4176 pnpm exec playwright test --project=mock e2e/product-center.spec.ts e2e/product-selection.spec.ts --workers=1` | 4 项 PASS：导航/history、四主题与 AI framed 对照、候选全量排序分页/图片预览/屏蔽恢复、策略抽屉/父级全部/校验/独立立即获取/hourly 与 daily 保存回读/百应不可用 |
| `PLAYWRIGHT_FRONTEND_PORT=4176 pnpm exec playwright test --config playwright.selection-real.config.ts --workers=1` | 1 项 PASS：Real 不回退、不请求选品接口，普通团队取消模块权限后拒绝直达。仅拦截现有登录/团队/权限 API，没有假设后端业务接口 |
| `git diff --check` | PASS |

候选列表使用原生降序→升序→取消排序，字段限上架日期/差评率；默认恢复夹具顺序，同值按字符串候选 ID 稳定，null 双向末尾，真实 0 参与排序。图片按既有 `--control-height-default` 尺寸组合，不修改标准行高；固定列为复选框/店铺/图片与右操作列，表格内部横向滚动。

实际浏览器截图（四主题、1366×768、横向滚动、策略列表、右抽屉、详情、填值后抽屉滚动、Real 不可用）保存在忽略目录 `docs/_local/product-selection-frontend-v1/{mock-browser,real-browser}/`。截图已检查，但不是 Electron 验收。

未执行项：唯一 Integration Electron 的视觉/操作验收由 ca97 在 Gate 2 完成；真实平台条件匹配、类目 API、达人登录/Session、持久化策略、正式采集/入库、后台定时与手机能力均未接入。未定义的“更多”日期选项、金额单位保留未知。百应条件为空且不生成模拟取数结果。

回滚：未涉及 Schema、数据或 Electron 壳变更；候选失败退回本 Feature，集成后回滚使用明确 revert，不改共享历史。无需新桌面包。状态为“前端／Mock完成，待 Gate 2”，不是选品业务完成或生产发布。
