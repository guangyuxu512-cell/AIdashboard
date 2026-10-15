# 全局列表竖线 — 共享增量 Gate 1

- 人类原始授权：规划 turn `01a13e0d-f1df-7cb1-977d-70262e09218c`（短标题、沿原居中、全局竖线）。不是新原生验收或发布批准。
- 原候选池 `b99f4265a35744f854e03f1ffb0320e9c9dafe17` 保留；纯共享分支 `feat/compact-product-list-foundation-v1` 从 `6ac6638be37026edb20fb8023ab4a4b7661e53c2` 正常追加，不含0046业务。
- 运行修改只有 `frontend/src/shared/ui/AppTable.vue`：既有 `NDataTable.singleLine` 统一 false，使用原生 1px 竖向列分隔。borderColor 已由既有四主题 `--border-subtle` 提供；不增颜色／边框框架／逐页CSS，不改外框bordered／stripe／选中／固定列／排序分页／原居中和grid业务对齐。
- 12px／28px／48px密度仍仅显式消费者使用，不是全局密度。详情 NDescriptions 原边框不改、不叠双线。无 ProductInfoCell API 增量；候选池标题预算在其局部列宽解决。

## 覆盖核查

当前分支 `frontend/src` 的非测试源搜索 `NDataTable`／`NTable`／`<table`：NDataTable 仅 AppTable；无 NTable／原生 HTML table 绕行。17个业务 DataTable 消费入口经 Shared DataTable→AppTable，经营看板另直接使用 AppTable。覆盖店铺、设备、参数、任务、计划、权限、日志、模型、资产、生成记录、选品列表和经营列表。

例外：AI工作台的卡片／树／自定义 div 列表、占位空态、详情描述表格不是 AppTable 列表，不人为加线。7d55未合入页面不在本分支核查范围；其消费精确新共享依赖须等ca97放行，不称跨未合分支全仓已覆盖。竖线由原生单元格边框贯穿表头和实际数据行，分页区域不增加线；不伪造空态网格。

## 验证

- 5文件23项：`pnpm exec vitest run src/shared/ui/AppTable.spec.ts src/shared/components/DataTable.spec.ts src/features/shop-management/ui/ShopListTable.spec.ts src/features/product-selection/ui/StrategyList.spec.ts src/features/operating-dashboard/ui/OperatingDashboardTable.spec.ts --maxWorkers=4` 通过，10.75s。AppTable覆盖grid/list、外框与stripe不变、selection/sorter透传、fill及左右固定列配置；修正测试rowClass类型收窄后再次定向验证。
- `pnpm typecheck`、受影响eslint通过；类型收窄后的AppTable3项再次通过。不重复699或后端。
- 浏览器仅4176 strictPort Mock；`pnpm exec playwright test --config ../.codex/selection-product-info-mock.config.ts --grep 'global column dividers' --reporter=line` 四主题4项通过（13.6s）。新 `e2e/global-table-dividers.spec.ts` 复用现有Playwright，实际检查四主题店铺／策略／经营：表头／正文1px solid同语义色、默认14px／34px未变、勾选与右固定操作横滚；外部/API请求0、pageerror0。实际截图位于被忽略的 `.codex/selection-product-info-mock/global-table-dividers-*/{theme}-{shops,strategies,operating}-vertical-dividers.png`。
- 浏览器首轮存在路由切换时误查旧页面表格的测试竞态，改为等待各页面自己的表格根节点，未改业务等待／未放宽边框断言。截图是实际Mock页面，不是Electron。
- 本增量无 Backend／DB／Migration／平台请求／Electron／依赖／清理；已有6ac默认隔离及699证据复用。

新共享精确SHA随提交推送交接，原Feature再正常no-ff消费后交完整候选；Root统一精确Real构建与唯一Electron。本共享自检不代表新布局原生确认或整体Gate2通过；不合dev/main、不发布。
