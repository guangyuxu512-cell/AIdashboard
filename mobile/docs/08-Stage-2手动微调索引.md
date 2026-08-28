# Stage 2 手动微调索引

本文是 Dimensions / Spacing / Typography（尺寸 / 间距 / 字体排版）的定位地图，不是新的设计规则。
当前数值均为 Stage 1 实现基线；修改前先确认 `02-设计系统.md` 的 Frozen Contract（冻结契约）。

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

改变以上任一项都属于 Unfreeze（解冻），必须先明确提出并重新确认。Stage 2 只调尺寸、间距、字体与
图标尺寸；颜色、圆角、阴影和图标视觉属于 Stage 3，Press / Motion（按压 / 动效）属于 Stage 4。

## 最常改

| 想调整什么       | 文件                           | Token / 位置                                           | 当前值      | 影响                                       |
| ---------------- | ------------------------------ | ------------------------------------------------------ | ----------- | ------------------------------------------ |
| 页面左右留白     | `src/shared/styles/tokens.css` | `--layout-page-padding-x`                              | 16px        | Header、Summary、Toolbar、列表与详情页     |
| 详情页上下留白   | `src/shared/styles/tokens.css` | `--layout-page-padding-y`                              | 16px        | `AppPage` 顶部与底部                       |
| 详情区块间距     | `src/shared/styles/tokens.css` | `--layout-section-gap`                                 | 16px        | Device / Task Detail 各业务 Section        |
| 列表卡片间距     | `src/shared/styles/tokens.css` | `--layout-card-gap`                                    | 12px        | Device / Task 列表                         |
| 卡片内部空间     | `src/shared/styles/tokens.css` | `--layout-card-padding`                                | 16px        | `DeviceCard`、`TaskCard`                   |
| 卡片图标到正文   | `src/shared/styles/tokens.css` | `--space-3`                                            | 12px        | Device / Task Card、`DeviceRuntimeSummary` |
| 卡片三行内部间距 | `src/shared/styles/tokens.css` | `--space-1`                                            | 4px         | Device / Task Card 主内容                  |
| 卡片标题字体     | `src/shared/styles/tokens.css` | `--font-size-label` / `--line-height-label`            | 15px / 20px | 设备名、任务名、Section 与能力标题         |
| 概览横幅高度     | `src/shared/styles/tokens.css` | `--layout-summary-height`                              | 98px        | `MobileSummaryStrip`                       |
| 工具行与紧凑控件 | `src/shared/styles/tokens.css` | `--layout-toolbar-height` / `--control-height-compact` | 44px / 32px | `MobileListToolbar`、Capability 轻操作     |
| 能力面板总高度   | `src/shared/styles/tokens.css` | `--layout-capability-panel-height`                     | 334px       | 五行完整显示与第六行起内部滚动             |

## Stage 2 常调参数

### A. Layout Dimensions（布局尺寸）

| 参数                                 | 当前值 | 主要影响                                                   |
| ------------------------------------ | ------ | ---------------------------------------------------------- |
| `--layout-content-max-width`         | 430px  | `MobileAppShell` 最大内容宽度                              |
| `--layout-header-height`             | 52px   | `MobileGlobalHeader` 内容高度，不含顶部 Safe Area          |
| `--layout-detail-header-height`      | 50px   | `MobileDetailHeader`；也映射到筛选 Sheet 的 Vant NavBar    |
| `--layout-summary-height`            | 98px   | `MobileSummaryStrip` 整体高度                              |
| `--layout-toolbar-height`            | 44px   | `MobileListToolbar` 整体高度                               |
| `--layout-bottom-nav-height`         | 58px   | Vant Tabbar 与五入口 Bottom Navigation，不含底部 Safe Area |
| `--layout-capability-panel-height`   | 334px  | `CapabilityPanel` 总高度                                   |
| `--layout-capability-row-min-height` | 44px   | Capability Row 最小高度                                    |

`MobileAppShell` 的 `100dvh`、Safe Area 所有权和 Header / Main / Bottom 三行 Grid 属于冻结的高度链与
滚动结构，不是 Stage 2 常规调参项。

### B. Spacing（间距）

| 语义                                     | 控制位置                  | 当前值    | 主要影响                                      |
| ---------------------------------------- | ------------------------- | --------- | --------------------------------------------- |
| Page Horizontal Padding（页面左右留白）  | `--layout-page-padding-x` | 16px      | Header、Summary、Toolbar、List、`AppPage`     |
| Page Vertical Padding（页面上下留白）    | `--layout-page-padding-y` | 16px      | `AppPage`                                     |
| Section Gap（区块间距）                  | `--layout-section-gap`    | 16px      | 详情页一级区块                                |
| Card Gap（卡片间距）                     | `--layout-card-gap`       | 12px      | Device / Task Infinite List                   |
| Card Padding（卡片内边距）               | `--layout-card-padding`   | 16px      | `DeviceCard`、`TaskCard`                      |
| Inner Gap（卡片内部间距）                | `--space-1`               | 4px       | 两类业务卡三行内容、Toolbar 紧凑控件          |
| Icon Content Gap（图标与正文距离）       | `--space-3`               | 12px      | Device / Task Card、`DeviceRuntimeSummary`    |
| Toolbar Gap（工具行组间距）              | `--space-2` / `--space-1` | 8px / 4px | Toolbar 左右组、Action 与控件内部             |
| Capability Row Gap（能力行内部间距）     | `--space-2`               | 8px       | Icon Slot、名称与 Actions                     |
| Detail Surface Padding（详情表面内边距） | `--space-4`               | 16px      | Task Summary/Core、Runtime Summary 分区与日志 |

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

| 图标位置                                  | 当前控制位置                                                             | 当前值      |
| ----------------------------------------- | ------------------------------------------------------------------------ | ----------- |
| Global Header Theme / Bell                | `--icon-size-default`                                                    | 22px        |
| Detail Header Back                        | `--icon-size-default`                                                    | 22px        |
| Bottom Navigation Icon                    | `vant-theme.css` → `--van-tabbar-item-icon-size` → `--icon-size-default` | 22px        |
| Summary Metric Icon                       | `--icon-size-default`                                                    | 22px        |
| DeviceCard / TaskCard Leading Slot / Icon | `--layout-card-leading-icon-slot-width` / `--icon-size-default`          | 22px / 22px |
| DeviceCard / TaskCard Chevron             | `--icon-size-small`                                                      | 16px        |
| DeviceRuntimeSummary Slot / Icon          | `--layout-runtime-summary-icon-slot-width` / `--icon-size-default`       | 22px / 22px |
| Capability Row Icon Slot / Icon           | `--layout-capability-icon-slot-width` / `--icon-size-small`              | 22px / 16px |

Header 与 Summary 的 Icon Box 继续直接消费图标尺寸；Device/Task Card、DeviceRuntimeSummary 与
Capability Row 已分别建立稳定 Slot Width Token。最终图标图案、描边与资源属于 Stage 3。

### E. Controls（控件尺寸）

| 参数                                 | 当前值 | 主要影响                                                             |
| ------------------------------------ | ------ | -------------------------------------------------------------------- |
| `--touch-target-min`                 | 44px   | Back、Theme、Bell、Summary Metric、Toolbar Action、Capability Action |
| `--control-height-compact`           | 32px   | Toolbar 控件视觉高度、Capability Refresh 视觉区域                    |
| `--control-height-default`           | 44px   | Vant 默认 Button 与 Search Input                                     |
| `--control-height-large`             | 50px   | Vant 大号 Button 与 Calendar Day                                     |
| `--control-height-capability-action` | 28px   | Capability Configure / Run 内部视觉高度                              |

`MobileListToolbar` 的 Action 外层保持 44px Touch Target，内部视觉控件为 32px；Capability Action 外层同样
保持 44px，文字视觉区域由 `--control-height-capability-action` 独立控制。调整视觉尺寸不得压缩 Touch
Target。

### F. Card Dimensions（卡片尺寸）

`DeviceCard` 与 `TaskCard` 没有固定 Height Token。当前高度由三行冻结结构、字体行高、
`--layout-card-padding`、`--space-1` 行间距和内容自然计算。Stage 2 可以统一微调这些数值，但不得增加或
删除行、改变 Leading / Main / Trailing 槽位，或写死两类卡片高度。

### G. Detail Density（详情页密度）

| 控制位置                                                               | 当前值                    | 主要影响                                                      |
| ---------------------------------------------------------------------- | ------------------------- | ------------------------------------------------------------- |
| `--layout-page-padding-x / y`                                          | 16px / 16px               | `AppPage` 四周内容留白                                        |
| `--layout-section-gap`                                                 | 16px                      | Device / Task Detail 一级 Section 距离                        |
| `--space-3`                                                            | 12px                      | 详情 Section 内标题/内容、Task Summary/Core 间距              |
| `--space-4`                                                            | 16px                      | Task Summary/Core 与 Runtime Log 内边距、Runtime Summary 分区 |
| `--space-6`                                                            | 24px                      | Device / Task Detail 当前底部内容留白                         |
| Vant Cell `font / line-height / vertical padding / horizontal padding` | 14px / 20px / 12px / 16px | “更多信息”与筛选列表密度                                      |
| Vant Collapse Content Padding                                          | 12px 16px                 | “更多信息”展开内容密度                                        |

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
- 左右留白：`--layout-page-padding-x` 与 Safe Area 的 `max()`；不要改变三列对称结构。

### MobileGlobalHeader（移动端全局顶部栏）

- 高度：`--layout-header-height`。
- 品牌字体：Title 字阶与 Semibold 字重。
- Theme / Bell 图标：`--icon-size-default`；触控区：`--touch-target-min`。
- 左右留白：`--layout-page-padding-x`；两操作间距：`--space-1`。

### MobileBottomNavigation（底部主导航）

- 高度：`--layout-bottom-nav-height`。
- 图标、文字与图文 Gap：`vant-theme.css` 的 Tabbar 映射，最终回到
  `--icon-size-default`、Caption 字阶和 `--space-1`。
- 不调整五等分、入口顺序、Shell Footer 或 Bottom Safe Area 所有权。

### MobileSummaryStrip（移动端概览横幅）

- 高度：`--layout-summary-height`；左右留白：`--layout-page-padding-x`。
- Metric Icon：`--icon-size-default`；Number：Display 字阶 + Bold；Label：Caption + Medium。
- 三层间距：`--space-1`；Metric 水平 Padding 与 Strip 顶部 Padding：`--space-2`。
- 不调整三等分、Icon → Number → Label 顺序或快捷筛选状态边界。

### MobileListToolbar（移动端列表工具行）

- 工具行高度：`--layout-toolbar-height`；Action Touch：`--touch-target-min`；视觉高度：
  `--control-height-compact`。
- 标题：Label 字阶 + Semibold；Meta：Caption 字阶。
- 左右留白：`--layout-page-padding-x`；左右组 Gap：`--space-2`；组内 Gap：`--space-1`。
- 不调整单行、Title + Meta / Selector + Filter 分组或滚动区位置。

### DeviceCard（设备卡片）

- Padding：`--layout-card-padding`；卡间距：列表容器的 `--layout-card-gap`。
- Leading 到正文：`--space-3`；正文三行 Gap：`--space-1`。
- Leading Slot / Icon：`--layout-card-leading-icon-slot-width` 22px / Default 22px；Chevron：Small 16px。
- 标题 / Runtime / Meta：Label 15/20、Secondary 13/18、Caption 12/16。
- 高度自然计算；不增加第四行或改写 Main / Trailing 槽位。

### TaskCard（任务卡片）

- Padding、列 Gap、正文三行 Gap、Leading Slot / Icon 与 Chevron 与 DeviceCard 相同。
- Task Name：Label 15/20；Status、Time 与 Meta：Caption 12/16；Tag 由 Vant Tag Mapping 控制。
- 高度自然计算；不增加 Progress / Current Message 或改变三行结构。

### DeviceRuntimeSummary（设备运行摘要）

- 上下分区 Padding：`--space-4`；Icon 到正文：`--space-3`；正文内部 Gap：`--space-1`。
- 两段 Icon Slot / Icon：`--layout-runtime-summary-icon-slot-width` / `--icon-size-default`，均为 22px；
  Value：Label 15/20；Label / Meta：Caption 12/16。
- Retry Touch：`--touch-target-min`。不要改变 Upper → Separator → Lower 或两段字段层级。

### CapabilityPanel（能力面板）

- 总高度：`--layout-capability-panel-height`，当前 334px。
- Panel Padding / Grid Gap：`--space-2` × `--space-3` / `--space-1`。
- Header 与 Selector 行：`--touch-target-min` 44px；Row 最小高度：
  `--layout-capability-row-min-height` 44px。
- Row Gap：`--space-2`；Icon Slot / Icon：`--layout-capability-icon-slot-width` 22px / Small 16px。
- Name：Body 14/20 + Medium；Version：Caption 12/16；Action：Touch 44px、
  `--control-height-capability-action` 28px、Action 13/18 + Medium。
- 调整总高度或 Row 密度后仍必须完整显示五行，并从第六行开始只滚动 Rows；Header / Selector 不滚动。

## 仍保留的局部值或当前无消费

- `mobile/src` 的生产业务组件已不存在直接写入的稳定 Stage 2 `px/rem/vh` 尺寸。
- Capability Refresh 的 `calc((Touch Target - Compact Control) / 2)` 只负责把视觉控件居中于触控热区；
  Segmented Selector、Safe Area 与 Summary 中的其余 `calc()` 同样属于局部结构数学，不建立额外 Token。
- `100%`、`100dvh / 100vh`、`minmax(0, 1fr)`、纯结构性 `0` 与 1px 分隔计算继续留在消费位置。
- `--layout-card-row-gap: 8px` 已定义但当前 `mobile/src` 没有消费；两类卡片实际使用 `--space-1: 4px`。
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
