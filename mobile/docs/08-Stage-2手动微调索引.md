# Stage 2 手动微调索引

本文是 Dimensions / Spacing / Typography（尺寸 / 间距 / 字体排版）的定位地图，不是新的设计规则。
当前数值是已完成 Stage 2 调整后的候选冻结基线（含 Final Polish B）；人工确认前不得重新开始无目的调参。修改前先确认
`02-设计系统.md` 的 Frozen Contract（冻结契约）与 Stage 2 Final Candidate Baseline。

## 冻结边界

Stage 1 已冻结 `MobileDetailHeader`、`MobileGlobalHeader`、`MobileBottomNavigation`、
`MobileSummaryStrip`、`MobileListToolbar`、`DeviceCard`、`TaskCard`、`DeviceRuntimeSummary` 与
`CapabilityPanel`。

手动微调不得改变：

- DOM 结构、组件顺序或业务字段层级。
- Grid / Flex 槽位关系与已冻结 Anatomy（结构）。
- Route、返回逻辑或 Bottom Navigation 的 Navigation Contract（导航约定）。
- Shell、List、Detail 与 Capability List 的 Scroll Contract（滚动约定）。
- Touch Target（触控热区）不得低于 44×44px。

改变以上任一项都属于 Unfreeze（解冻），必须先明确提出并重新确认。已完成的 Stage 2 只收口尺寸、间距、
字体与图标尺寸；颜色、圆角、阴影和图标视觉属于 Stage 3，Press / Motion（按压 / 动效）属于 Stage 4。

## 最常改

| 想调整什么            | 文件                           | Token / 位置                                                              | 当前值                   | 影响                                       |
| --------------------- | ------------------------------ | ------------------------------------------------------------------------- | ------------------------ | ------------------------------------------ |
| 页面左右留白          | `src/shared/styles/tokens.css` | `--layout-page-padding-x`                                                 | 16px                     | Header、Summary、Toolbar、列表与详情页     |
| 详情页上下留白        | `src/shared/styles/tokens.css` | `--layout-page-padding-y`                                                 | 12px                     | `AppPage` 基础顶部与底部                   |
| 详情区块间距          | `src/shared/styles/tokens.css` | `--layout-section-gap`                                                    | 12px                     | Device / Task Detail 各业务 Section        |
| 列表卡片间距          | `src/shared/styles/tokens.css` | `--layout-card-gap`                                                       | 8px                      | Device / Task 列表                         |
| 卡片水平内边距        | `src/shared/styles/tokens.css` | `--layout-card-padding-x`                                                 | 12px                     | `DeviceCard`、`TaskCard`                   |
| 卡片垂直内边距        | `src/shared/styles/tokens.css` | `--layout-card-padding-y`                                                 | 16px                     | `DeviceCard`、`TaskCard`                   |
| 卡片图标到正文        | `src/shared/styles/tokens.css` | `--space-2`                                                               | 8px                      | Device / Task Card、`DeviceRuntimeSummary` |
| 卡片三行内部间距      | `src/shared/styles/tokens.css` | `--layout-card-row-gap`                                                   | 4px                      | Device / Task Card 主内容                  |
| 卡片标题字体          | `src/shared/styles/tokens.css` | `--font-size-label` / `--line-height-label`                               | 15px / 20px              | 设备名、任务名、Section 与能力标题         |
| 概览横幅高度          | `src/shared/styles/tokens.css` | `--layout-summary-height`                                                 | 96px                     | `MobileSummaryStrip`                       |
| 概览横幅上下边距      | `src/shared/styles/tokens.css` | `--layout-summary-padding-y`                                              | 8px                      | Summary Surface 与三层 Metric 的呼吸空间   |
| 工具行与紧凑控件      | `src/shared/styles/tokens.css` | `--layout-toolbar-height` / `--control-height-compact`                    | 44px / 30px              | `MobileListToolbar`、Capability 轻操作     |
| 主业务图标槽 / 图形   | `src/shared/styles/tokens.css` | `--layout-card-leading-icon-slot-width` / `--icon-size-card-leading`      | 44px / 28px              | `DeviceCard`、`TaskCard` 主视觉锚点        |
| 运行摘要内边距 / 图标 | `src/shared/styles/tokens.css` | `--layout-runtime-summary-padding-x / y`、Slot / Glyph                    | 12px / 16px、36px / 22px | `DeviceRuntimeSummary`                     |
| 能力面板总高度 / 行高 | `src/shared/styles/tokens.css` | `--layout-capability-panel-height` / `--layout-capability-row-min-height` | 354px / 48px             | 五行完整显示与第六行起内部滚动             |

## Stage 2 参数定位（候选冻结）

### A. Layout Dimensions（布局尺寸）

| 参数                                 | 当前值 | 主要影响                                                   |
| ------------------------------------ | ------ | ---------------------------------------------------------- |
| `--layout-content-max-width`         | 430px  | `MobileAppShell` 最大内容宽度                              |
| `--layout-header-height`             | 52px   | `MobileGlobalHeader` 内容高度，不含顶部 Safe Area          |
| `--layout-detail-header-height`      | 50px   | `MobileDetailHeader`；也映射到筛选 Sheet 的 Vant NavBar    |
| `--layout-summary-height`            | 96px   | `MobileSummaryStrip` 整体高度                              |
| `--layout-summary-padding-y`         | 8px    | Summary Surface 上下边距                                   |
| `--layout-toolbar-height`            | 44px   | `MobileListToolbar` 整体高度                               |
| `--layout-bottom-nav-height`         | 58px   | Vant Tabbar 与五入口 Bottom Navigation，不含底部 Safe Area |
| `--layout-capability-panel-height`   | 354px  | `CapabilityPanel` 总高度                                   |
| `--layout-capability-row-min-height` | 48px   | Capability Row 最小高度                                    |

`MobileAppShell` 的 `100dvh`、Safe Area 所有权和 Header / Main / Bottom 三行 Grid 属于冻结的高度链与
滚动结构，不是 Stage 2 常规调参项。

### Final Polish B 候选记录（内容 Surface 与 Icon 容量）

Status（状态）: Completed / Candidate for Freeze（已完成 / 待人工确认冻结）。本记录是当前尺寸的权威来源；
下方 Stage 2C / 2D / 2F 原始结论仅保留为演进记录，若与本节冲突，以本节为准。

| 项目                                | 实测候选                                                        | 推荐候选        | 结论                                                          |
| ----------------------------------- | --------------------------------------------------------------- | --------------- | ------------------------------------------------------------- |
| Summary Strip                       | 88px、92px、96px；上下边距均 8px                                | 96px / 8px      | Surface 80px，三层内容上下各约 7px，不变成 Dashboard。        |
| Runtime Summary Padding Y           | 12px、14px、16px；X 固定 12px                                   | X 12px / Y 16px | 仅舒展上下两段，不扩大左右正文起点。                          |
| Capability Row / Panel              | 44px / 334px、48px / 354px、52px / 374px                        | 48px / 354px    | 354px 经真实盒模型校验后完整容纳 5 行；第 6 行只在内部滚动。  |
| Primary Leading Visual              | 32px / 20px、40px / 24px、44px / 28px、48px / 28px、48px / 32px | 44px / 28px     | 明确主业务扫描锚点，同时在 360px 保留名称单行 Ellipsis 空间。 |
| Runtime Leading Visual              | 32px / 20px、36px / 22px、40px / 24px                           | 36px / 22px     | 低于 Primary Leading Visual，不与主卡片争夺视觉重量。         |
| Capability / Summary / Control Icon | 28px / 16px、20px、22px                                         | 保持            | 能力列表维持密度；概览数字优先；操作图标不参与本轮放大。      |

Stage 3 才决定正式图标资源、Tile 背景、颜色、圆角、阴影和最终 SVG / PNG；本节只冻结候选中的尺寸与占位容量，
不冻结上述视觉属性。

### Stage 2C 历史结论（全局尺寸比例）

| 区域              | Stage 2C 最终值 | 结论                                                                                       |
| ----------------- | --------------- | ------------------------------------------------------------------------------------------ |
| Global Header     | 52px            | 保持；完整容纳品牌与两个 44px Touch Target。                                               |
| Detail Header     | 50px            | 保持；返回 Touch Target 与居中标题比例协调。                                               |
| Summary Strip     | 88px            | 从 98px 调整；实测 98 / 92 / 88 / 84px，84px 已接近三层内容的最小高度，88px 保留舒适留白。 |
| List Toolbar      | 44px            | 保持；是工具行与 Touch Target 的稳定基线。                                                 |
| Bottom Navigation | 58px            | 保持；不含 Bottom Safe Area，五入口不拥挤。                                                |

本轮历史结论不再代表当前候选；Final Polish B 已只调整内容型 Surface 和图标容量。Safe Area 与 `100dvh`
Shell 高度链仍独立于上述内容高度。

### Stage 2D / Final Polish B 结论（Card / Icon Ratio）

| 区域                          | Slot / Icon 最终值 | 结论                                         |
| ----------------------------- | ------------------ | -------------------------------------------- |
| DeviceCard / TaskCard Leading | 44px / 28px        | 主业务扫描锚点，360px 仍保留单行名称空间。   |
| DeviceCard / TaskCard Chevron | 24px / 16px        | 保持弱化箭头视觉，同时提供稳定右侧槽位。     |
| DeviceRuntimeSummary          | 36px / 22px        | 低于主业务卡片的上下分区视觉锚点。           |
| Capability Row                | 28px / 16px        | 图标保持克制，不挤压名称、版本与 Actions。   |
| MobileSummaryStrip Metric     | 20px               | 数字继续由 Display + Bold 承担最高信息权重。 |

Header、Detail Header、Bottom Navigation 的 22px Control Icon 映射保持不变。Final Polish B 只调整 Summary、
Runtime、Capability Row / Panel 与 Primary Leading Visual；Card Padding、Gap、Typography、Control 尺寸均保持。

### Stage 2E 结论（控件视觉尺寸与触控热区）

| 区域                       | Visual Size | Touch Target               | 结论                                                                    |
| -------------------------- | ----------- | -------------------------- | ----------------------------------------------------------------------- |
| Toolbar Selector / Filter  | 30px 高     | 各自 44px 高、至少 44px 宽 | 同级、同中心、按内容定宽，360px 保持一行且不重叠。                      |
| Capability Configure / Run | 28px 高     | 各自至少 44×44px           | 保持轻量文字 Shell，Configure 在 Run 左侧，不改变 Capability Row 高度。 |
| Capability Refresh         | 30×30px     | 44×44px                    | Header 右侧 Section 级轻操作，不抢占主信息。                            |
| Global Header Theme / Bell | 34×34px     | 各自 44×44px               | 两者完全同尺寸，在 52px Header 内居中；图标仍为 22px。                  |
| Vant Default Button        | 44px 高     | 44px                       | 保持标准 CTA / 输入基线，不因紧凑业务控件而全局压缩。                   |

控件的可见 Shell 与点击范围是两套职责：只对明确的 Toolbar、Capability 与 Shared Icon Button 语义应用紧凑
Token；禁止创建 `device-filter-height`、`task-action-height` 等 Feature 私有 Token，禁止用透明 Overlay 扩大
命中区并遮挡相邻操作。Stage 2E 不调整 Typography、Spacing、Global Dimensions、Icon Ratio、Capability Panel /
Row 高度、Color、Radius、Shadow、Press 或 Motion。

### Stage 2F 结论（详情页纵向密度）

| 区域                 | Stage 2F 最终值 / 结论 | 依据与边界                                                                             |
| -------------------- | ---------------------- | -------------------------------------------------------------------------------------- |
| DeviceRuntimeSummary | 保持自然高度           | 没有固定 Height / Min Height；由 Frozen 两段内容、X 12px / Y 16px Padding 与行高决定。 |
| Capability Panel     | 354px                  | 真实盒模型校验后完整显示 5 行；不得露出第 6 行。                                       |
| Capability Row       | 最小 48px              | Configure / Run 各自保留至少 44×44px Touch Target；不以多塞一行换密度。                |
| Capability List      | 第 6 行起内部滚动      | Header / Selector 固定，只有 Rows 滚动；5 行时无多余滚动范围。                         |
| Task Detail          | 保持自然高度           | Summary、Core、Runtime Log 无局部固定高度；不删字段、不改顺序或滚动职责。              |

主人工基准为 `390 × 844` 的 Visual Mock viewport：Device Detail 首屏先展示运行摘要与能力区；Task Detail
首屏先展示 Summary / Core，并使 Runtime Log 标题进入可见区域。360 / 375 / 430px 和 Light / Dark 只验证相同
密度语言、无横向溢出、Touch Target 与内部滚动契约。以上是 Stage 2F 的详情密度结论；最终冻结状态以随后的
Stage 2 Final Baseline 为准。

### Stage 2 Final Baseline（第二阶段最终基线）

Status（状态）: Completed / Candidate for Freeze（已完成 / 待人工确认冻结）

Final Review 已把 Typography、Spacing、Global Dimensions、Card / Icon Ratio、Controls 与 Detail Density
放回完整页面复核。390 × 844 Light 的四个主页面和 360 / 375 / 430px Light、390px Dark 已比较 Card Y
`12 / 14 / 16px`（最终 Y `16px`）与 Final Polish B 的内容 Surface / Icon 候选；当前推荐组合以本文件
“Final Polish B 候选记录”为准。按 `mobile/AGENTS.md`，自动验证与 Review 不替代人工视觉确认；人工确认后
才将此状态更新为 `Frozen`。

- Typography：`12 / 13 / 14 / 15 / 16 / 18px` 与对应 `16 / 18 / 20 / 20 / 22 / 22px` Line Height，按
  Regular / Medium / Semibold / Bold 的既定角色消费。
- Spacing：`4 / 8 / 12 / 16 / 20 / 24 / 32px`；Page `16 / 12px`、Section `12px`、Card `8 / 12 / 4px`。
- Dimensions：Global Header `52px`、Detail Header `50px`、Summary `96px`、Toolbar `44px`、Bottom Nav
  `58px`。
- Card / Icon：Primary Leading Visual `44 / 28px`、Chevron `24 / 16px`、Runtime Leading Visual `36 / 22px`、Capability `28 / 16px`、
  Summary `20px`。
- Controls：Compact `30px`、Capability Action `28px`、Header Icon Shell `34px`、Touch Target `44×44px`。
- Detail：Capability Panel `354px`、Row `48px`、Runtime / Task Detail 自然高度；5 行完整、第 6 行起内部滚动。

候选冻结的是这组经页面级验证的默认尺寸基线，不是永久禁止改动。人工确认前不得重新开始无目的调参；只有真实设备、
正式图标或新增业务页面带来可复现的比例问题时，才可通过显式 Review 调整。人工确认后，该规则以 Frozen Baseline
继续执行。Color、Surface、Radius、Border、Shadow、Final Icon、Press 与 Motion 仍属于未冻结的 Stage 3 / 4 范围。

### B. Spacing（间距）

| 语义                                            | 控制位置                                 | 当前值      | 主要影响                                   |
| ----------------------------------------------- | ---------------------------------------- | ----------- | ------------------------------------------ |
| Page Horizontal Padding（页面左右留白）         | `--layout-page-padding-x`                | 16px        | Header、Summary、Toolbar、List、`AppPage`  |
| Page Vertical Padding（页面上下留白）           | `--layout-page-padding-y`                | 12px        | `AppPage`                                  |
| Section Gap（区块间距）                         | `--layout-section-gap`                   | 12px        | 详情页一级区块                             |
| Card Gap（卡片间距）                            | `--layout-card-gap`                      | 8px         | Device / Task Infinite List                |
| Card Padding X（卡片左右内边距）                | `--layout-card-padding-x`                | 12px        | `DeviceCard`、`TaskCard`                   |
| Card Padding Y（卡片上下内边距）                | `--layout-card-padding-y`                | 16px        | `DeviceCard`、`TaskCard`                   |
| Inner Gap（卡片内部间距）                       | `--layout-card-row-gap`                  | 4px         | 两类业务卡三行内容                         |
| Icon Content Gap（图标与正文距离）              | `--space-2`                              | 8px         | Device / Task Card、`DeviceRuntimeSummary` |
| Toolbar Gap（工具行组间距）                     | `--space-2` / `--space-1`                | 8px / 4px   | Toolbar 左右组、Action 与控件内部          |
| Capability Row Gap（能力行内部间距）            | `--space-2`                              | 8px         | Icon Slot、名称与 Actions                  |
| Runtime Summary Padding X / Y（运行摘要内边距） | `--layout-runtime-summary-padding-x / y` | 12px / 16px | DeviceRuntimeSummary 上下分区              |
| Detail Surface Padding（详情表面内边距）        | `--space-4`                              | 16px        | Task Summary/Core 与 Runtime Log           |

`--space-*` 是全局比例尺，同一个值会影响多个组件。若只想改某个组件，先查看“按组件找参数”，不要
直接修改全局比例尺后只检查单页。

### C. Typography（字体排版）

| 字体角色             | Token                                               | 当前值      | 字重 | 主要影响                                              |
| -------------------- | --------------------------------------------------- | ----------- | ---- | ----------------------------------------------------- |
| Caption / Meta       | `--font-size-caption` / `--line-height-caption`     | 12px / 16px | 400  | 时间、心跳、Meta、Tag、Summary Label、日志辅助信息    |
| Secondary            | `--font-size-secondary` / `--line-height-secondary` | 13px / 18px | 400  | Device Runtime 与普通辅助内容                         |
| Action               | `--font-size-action` / `--line-height-action`       | 13px / 18px | 500  | Vant Button、Toolbar、Capability Selector / Action    |
| Body                 | `--font-size-body` / `--line-height-body`           | 14px / 20px | 400  | 正文、Vant Cell                                       |
| Capability Name      | Body Size / Line Height + Medium Weight             | 14px / 20px | 500  | Application / Skill Name                              |
| Section / Card Title | `--font-size-label` / `--line-height-label`         | 15px / 20px | 600  | Toolbar、Device/Task Card、Section、Capability Header |
| Brand / Header       | `--font-size-title` / `--line-height-title`         | 16px / 22px | 600  | 品牌、详情 Header、Task Detail 标题                   |
| Summary Number       | `--font-size-display` / `--line-height-display`     | 18px / 22px | 700  | `MobileSummaryStrip` 数字                             |

字重分别由 `--font-weight-regular`（400）、`--font-weight-medium`（500）、
`--font-weight-semibold`（600）和 `--font-weight-bold`（700）控制。修改这些全局字重会同时影响所有同角色
组件。

### D. Icon Dimensions（图标尺寸）

| 图标位置                                  | 当前控制位置                                                               | 当前值      |
| ----------------------------------------- | -------------------------------------------------------------------------- | ----------- |
| Global Header Theme / Bell                | `--icon-size-default`                                                      | 22px        |
| Detail Header Back                        | `--icon-size-default`                                                      | 22px        |
| Bottom Navigation Icon                    | `vant-theme.css` → `--van-tabbar-item-icon-size` → `--icon-size-default`   | 22px        |
| Summary Metric Icon                       | `--icon-size-summary-metric`                                               | 20px        |
| Primary Leading Visual Slot / Glyph       | `--layout-card-leading-icon-slot-width` / `--icon-size-card-leading`       | 44px / 28px |
| DeviceCard / TaskCard Chevron Slot / Icon | `--layout-card-trailing-icon-slot-width` / `--icon-size-card-chevron`      | 24px / 16px |
| Runtime Leading Visual Slot / Glyph       | `--layout-runtime-summary-icon-slot-width` / `--icon-size-runtime-summary` | 36px / 22px |
| Capability Row Icon Slot / Icon           | `--layout-capability-icon-slot-width` / `--icon-size-capability-row`       | 28px / 16px |

Header、Detail Header 与 Bottom Navigation 继续直接消费 `--icon-size-default` 22px。Primary Leading Visual、
Runtime Leading Visual、Capability Icon、Summary Icon 与 Control Icon 已分别建立语义尺寸角色；最终图标图案、
描边、Tile 与资源属于 Stage 3。

### E. Controls（控件尺寸）

| 参数                                 | 当前值 | 主要影响                                                             |
| ------------------------------------ | ------ | -------------------------------------------------------------------- |
| `--touch-target-min`                 | 44px   | Back、Theme、Bell、Summary Metric、Toolbar Action、Capability Action |
| `--control-height-compact`           | 30px   | Toolbar 控件视觉高度、Capability Refresh 视觉区域                    |
| `--control-size-icon-button`         | 34px   | Theme / Bell / Detail Back 的可见图标按钮外壳                        |
| `--control-height-default`           | 44px   | Vant 默认 Button 与 Search Input                                     |
| `--control-height-large`             | 50px   | Vant 大号 Button 与 Calendar Day                                     |
| `--control-height-capability-action` | 28px   | Capability Configure / Run 内部视觉高度                              |

`MobileListToolbar` 的 Action 外层保持 44px Touch Target，内部视觉控件为 30px；Capability Action 外层
同样保持至少 44×44px Touch Target，文字视觉区域由 `--control-height-capability-action` 独立控制。Refresh
使用 30px 可见 Shell；Theme / Bell / Detail Back 通过 `--control-size-icon-button` 使用 34px 可见 Shell，
但三者外层仍是 44×44px。Capability Action 与 Toolbar Action 的相邻热区必须独立，不得重叠。

### F. Card Dimensions（卡片尺寸）

`DeviceCard` 与 `TaskCard` 没有固定 Height Token。当前高度由三行冻结结构、字体行高、
`--layout-card-padding-x`、`--layout-card-padding-y` 与 `--layout-card-row-gap` 行间距和内容自然计算。X 固定
`12px`、Y 候选为 `16px`；这些数值已纳入 Stage 2 Final Candidate Baseline，人工确认前不得继续随意微调，
更不得增加或删除行、改变 Leading / Main / Trailing 槽位，或写死两类卡片高度。

### G. Detail Density（详情页密度）

| 控制位置                                                               | 当前值                    | 主要影响                                                            |
| ---------------------------------------------------------------------- | ------------------------- | ------------------------------------------------------------------- |
| `--layout-page-padding-x / y`                                          | 16px / 12px               | `AppPage` 四周内容留白                                              |
| `--layout-section-gap`                                                 | 12px                      | Device / Task Detail 一级 Section 距离                              |
| `--space-3`                                                            | 12px                      | 详情 Section 内标题/内容、Task Summary/Core 与 Runtime Summary 分区 |
| `--space-4`                                                            | 16px                      | Task Summary/Core 与 Runtime Log 内边距                             |
| `--space-6`                                                            | 24px                      | Device / Task Detail 当前底部内容留白                               |
| `--layout-capability-panel-height`                                     | 354px                     | 5 行 Capability 完整显示；第 6 行起仅内部滚动                       |
| `--layout-capability-row-min-height`                                   | 48px                      | Capability Row 与 Configure / Run 的触控约束                        |
| Vant Cell `font / line-height / vertical padding / horizontal padding` | 14px / 20px / 12px / 16px | “更多信息”与筛选列表密度                                            |
| Vant Collapse Content Padding                                          | 12px 16px                 | “更多信息”展开内容密度                                              |

## Vant 4 尺寸映射

统一入口为 `src/shared/styles/vant-theme.css`，只调整 Mobile Token 或该统一映射，不在 Page 使用
`:deep()` 私改尺寸。

| Vant 组件        | 真实尺寸映射                                                    | 当前生产用途                                            |
| ---------------- | --------------------------------------------------------------- | ------------------------------------------------------- |
| Button           | 默认 44px、大号 50px、Action 13/18px + Medium                   | Retry、筛选、Capability Actions                         |
| NavBar           | 高 50px、箭头 16px、标题 16/22px + Semibold                     | Task Filter Sheet 子页面；不是正式 `MobileDetailHeader` |
| Tabbar           | 高 58px、Icon 22px、文字 12/16px、图文 Gap 4px                  | `MobileBottomNavigation`                                |
| Tabs             | Touch/Wrap 44px、文字 13/18px + Medium                          | `CapabilityPanel` 类型选择器                            |
| Cell / CellGroup | 字体 14/20px、上下 12px、左右 16px                              | Device/Task More Information、设备筛选                  |
| Tag              | 字体 12/16px、上下 2px、左右 8px                                | Device/Task 状态与 Meta Tag                             |
| Search / Field   | Input 44px、Search 上下 8px/左右 12px                           | Task Filter Sheet                                       |
| Popup            | Surface 由 Vant Mapping；高度由 overlay Token 和业务 Sheet 组合 | Task Filter 与 Foundation Sheet                         |
| Calendar         | Header Action 44px、Day 50px、Selected 44px、Confirm 44px       | Task 日期筛选                                           |
| Picker           | Toolbar 44px                                                    | 已有统一映射，当前生产页面无直接消费                    |

## 按组件找参数

### MobileDetailHeader（移动端详情头部）

- 高度：`--layout-detail-header-height`。
- 标题：`--font-size-title`、`--line-height-title`、`--font-weight-semibold`。
- Back 图标与左右 Slot：`--icon-size-default`、`--touch-target-min`。
- Back 可见 Icon Button Shell：`--control-size-icon-button`；不改变 Detail Header 高度或三列结构。
- 左右留白：`--layout-page-padding-x` 与 Safe Area 的 `max()`；不要改变三列对称结构。

### MobileGlobalHeader（移动端全局顶部栏）

- 高度：`--layout-header-height`。
- 品牌字体：Title 字阶与 Semibold 字重。
- Theme / Bell 图标：`--icon-size-default`；可见 Icon Button Shell：`--control-size-icon-button`；触控区：`--touch-target-min`。
- 左右留白：`--layout-page-padding-x`；两操作间距：`--space-1`。

### MobileBottomNavigation（底部主导航）

- 高度：`--layout-bottom-nav-height`。
- 图标、文字与图文 Gap：`vant-theme.css` 的 Tabbar 映射，最终回到
  `--icon-size-default`、Caption 字阶和 `--space-1`。
- 不调整五等分、入口顺序、Shell Footer 或 Bottom Safe Area 所有权。

### MobileSummaryStrip（移动端概览横幅）

- 高度：`--layout-summary-height` 96px；左右留白：`--layout-page-padding-x`；上下边距：
  `--layout-summary-padding-y` 8px。
- Metric Icon：`--icon-size-summary-metric` 20px；Number：Display 字阶 + Bold；Label：Caption + Medium。
- 三层间距：`--space-1` 4px；96px 高度下 Surface 维持三层上下呼吸空间。
- 不调整三等分、Icon → Number → Label 顺序或快捷筛选状态边界。

### MobileListToolbar（移动端列表工具行）

- 工具行高度：`--layout-toolbar-height`；Action Touch：`--touch-target-min`；视觉高度：
  `--control-height-compact`。
- 标题：Label 字阶 + Semibold；Meta：Caption 字阶。
- 左右留白：`--layout-page-padding-x` 16px；左右组 Gap：`--space-2` 8px；组内 Gap：
  `--space-1` 4px。
- 不调整单行、Title + Meta / Selector + Filter 分组或滚动区位置。

### DeviceCard（设备卡片）

- Padding：`--layout-card-padding-x` 12px、`--layout-card-padding-y` 16px；卡间距：列表容器的
  `--layout-card-gap` 8px。
- Leading 到正文：`--space-2` 8px；正文三行 Gap：`--layout-card-row-gap` 4px。
- Primary Leading Visual Slot / Glyph：`--layout-card-leading-icon-slot-width` / `--icon-size-card-leading`，44px / 28px；
  Chevron Slot / Icon：`--layout-card-trailing-icon-slot-width` / `--icon-size-card-chevron`，24px / 16px。
- 标题 / Runtime / Meta：Label 15/20、Secondary 13/18、Caption 12/16。
- 高度自然计算；不增加第四行或改写 Main / Trailing 槽位。

### TaskCard（任务卡片）

- Padding X / Y、列 Gap、正文三行 Gap、Leading Slot / Icon 与 Chevron 与 DeviceCard 相同。
- Task Name：Label 15/20；Status、Time 与 Meta：Caption 12/16；Tag 由 Vant Tag Mapping 控制。
- 高度自然计算；不增加 Progress / Current Message 或改变三行结构。

### DeviceRuntimeSummary（设备运行摘要）

- 上下分区 Padding：`--layout-runtime-summary-padding-x / y` 12px / 16px；Icon 到正文：`--space-2` 8px；正文内部 Gap：
  `--space-1` 4px。
- 两段 Runtime Leading Visual Slot / Glyph：`--layout-runtime-summary-icon-slot-width` / `--icon-size-runtime-summary`，36px / 22px；
  Value：Label 15/20；Label / Meta：Caption 12/16。
- Retry Touch：`--touch-target-min`。不要改变 Upper → Separator → Lower 或两段字段层级。

### CapabilityPanel（能力面板）

- 总高度：`--layout-capability-panel-height`，当前 354px。
- Panel Padding / Grid Gap：垂直 `--space-2` 8px × 水平 `--space-3` 12px / `--space-1` 4px。
- Header 与 Selector 行：`--touch-target-min` 44px；Row 最小高度：
  `--layout-capability-row-min-height` 48px。
- Row Gap：`--space-2` 8px；Actions Gap：`--space-1` 4px；Icon Slot / Icon：
  `--layout-capability-icon-slot-width` / `--icon-size-capability-row`，28px / 16px。
- Name：Body 14/20 + Medium；Version：Caption 12/16；Action：Touch 44px、
  `--control-height-capability-action` 28px、Action 13/18 + Medium。
- 调整总高度或 Row 密度后仍必须完整显示五行，并从第六行开始只滚动 Rows；Header / Selector 不滚动。

## 仍保留的局部值或当前无消费

- `mobile/src` 的生产业务组件已不存在直接写入的稳定 Stage 2 `px/rem/vh` 尺寸。
- Capability Refresh 的 `calc((Touch Target - Compact Control) / 2)` 只负责把视觉控件居中于触控热区；
  Segmented Selector、Safe Area 与 Summary 中的其余 `calc()` 同样属于局部结构数学，不建立额外 Token。
- `100%`、`100dvh / 100vh`、`minmax(0, 1fr)`、纯结构性 `0` 与 1px 分隔计算继续留在消费位置。
- `--layout-card-row-gap: 4px` 已由 DeviceCard / TaskCard 共同消费，不再保留未使用的重复卡片行距。
- `--control-height-medium: 40px` 已定义但当前 `mobile/src` 没有消费。
- `MobileAppShell` 的 `100dvh / 100vh` 回退与 `base.css` 的 320px 最小宽度是平台边界，不是业务组件
  Stage 2 调参项。

## Stage 3 与 Stage 4 位置

- Stage 3：Light / Dark 颜色、Surface、Border、Radius 与 Shadow 的唯一值入口仍是
  `src/shared/styles/tokens.css`；Vant 只在 `vant-theme.css` 做统一映射。
- Stage 4：`--duration-*`、`--ease-press`、`--press-scale-*` 位于 `tokens.css`，统一 Press Class 位于
  `base.css`。
- 本索引不授权提前修改这些值，也不授权逐页建立颜色、圆角、阴影或 Motion。

## 手调后的最小验证

真正进入 Stage 2 调参后，每次至少运行 lint、typecheck、build 与 `git diff --check`，并在
360 / 375 / 390 / 430px 的 Light / Dark 下检查无横向溢出、Touch Target、Safe Area、五行 Capability
显示和冻结滚动关系。一次只改一组 Token，避免无法判断影响来源。
