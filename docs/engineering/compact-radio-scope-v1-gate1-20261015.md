# 共享Radio局部紧凑尺寸 — Gate 1

## 范围及前置取证

承接人类已确认12px／28px紧凑规格、商品数据复用授权，由规划正式分配唯一共享Owner81a1补遗漏映射。开工原候选池分支cbe30cb干净保留，正规串行切回纯共享 `feat/compact-product-list-foundation-v1`，直接接续 `1a8078d0cd9917afc11454e84ff0d13d15a1a2f2`；不合入选品0046／7d55业务。

已只读7d55：`docs/engineering/shop-product-data-compact-v1-preparation-20261015.md` 与原始 `frontend/test-results/product-data-compact-v3/report.json`。原始19项14通过／5失败：3个视口与1个可选筛选探针均明确期望12px／28px、实际14px／34px；另1跨页旧组件未卸载竞态已由7d55独立通过核销。本Owner没有修改该树／原断言／证据，不将原4项失败改写成通过。

`AppRadio.vue` 原实现固定 medium 的 `NRadioGroup → NRadioButton`。核对实际安装Naive 2.45的 `radio/styles/light.mjs` 与 `RadioGroup.mjs`：官方取值键为 `buttonHeightMedium`／`fontSizeMedium`，与Button的height键不同；旧局部profile确实未含Radio，并非动画或平台／页面数据问题。

## 最小实现

唯一生产代码差异：`shared/ui/list-density.ts` 的既有compact profile追加Radio四个尺寸字段（small/medium，复用 `--list-compact-control-height` / `--list-compact-font-size`）。不改AppRadio或全局 `naive-theme.ts`，不新增Token、API、控件、Provider或页面覆盖；默认density依旧undefined，父主题颜色原生不可变合并。

其它变更只定向单测、既有浏览器夹具／Radio测试和公共规范说明。候选池视觉／默认20、全局竖线、商品实体及其它业务均不改；无DB／Migration／平台／依赖／Electron／生产动作，不占4177/5180、不碰Profile。

## 实际验证

- `pnpm exec vitest run src/shared/components/list-density.spec.ts src/features/operating-dashboard/ui/OperatingDashboardFilterBar.spec.ts --maxWorkers=2`：2文件11项通过（7.09s）。Radio局部12/28、默认14/34、禁用与父颜色更新／不突变、切回default，以及既有经营日期快捷行为覆盖。
- 受影响eslint、当前`pnpm typecheck`、`git diff --check`通过。
- 使用已有Chromium headless shell：`pnpm exec playwright test --config playwright.compact-list.config.ts --grep 'Radio compact dimensions' --output ../.codex/compact-radio-20261015 --reporter=line`，4主题4项通过（11.3s）。4176 strictPort frontend-only，非业务路由夹具，外部/API请求0、pageerror0。
- 四主题实际DOM测量：局部四个Radio（含禁用项）12px／28px，选择30天成功；边界外默认Radio与兄弟Drawer内Radio均14px／34px；切回default恢复14/34、重新compact为12/28，选中值不丢。原默认Modal代码／provider路径未改，未额外冒称Modal专项原生验收。
- 实际夹具截图保留独立ignored目录 `.codex/compact-radio-20261015/compact-list-foundation-*/{theme}-radio-{scoped,drawer-default}.png`，不是商品数据页面或Electron证据。不重复未变699、全套历史视觉或平台采集。

## 交接与边界

精确纯共享Candidate随提交推送正式交ca97审核，再由其给7d55正常no-ff消费。本Owner不代改或merge对方树；7d55需在自己的新精确消费候选复跑原4项失败及相关默认Overlay检查，当前不能称b2ccc草稿Gate1完成。旧1a、cbe、全部Mock夹具、平台Session与数据保留。

未合dev/main、未部署、无新数据库/Slot；此小修不是商品数据新视觉批准、真实basic Gate通过或选品整体完成。回滚可正常revert此共享增量，无Schema或数据回滚。
