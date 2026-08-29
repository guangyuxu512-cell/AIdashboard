# Stage 2 手动微调索引

本文记录 Mobile Stage 2 的唯一正式尺寸基线。正式值以
`src/shared/styles/tokens.css` 为权威来源；本文件用于说明 Token 的职责、消费者与冻结边界，不能创建
第二套值。

## 状态与冻结范围

Status（状态）: **Completed / Frozen（已完成 / 已冻结）**

本次基线来自已完成的 Visual Token Tuner V1 人工微调。冻结范围为：

- Typography（字体排版）
- Spacing（间距）
- Global Dimensions（全局尺寸）
- Card / Icon Ratio（卡片与图标比例）
- Controls（控件尺寸）
- Detail Density（详情密度）

Stage 1 的 Anatomy（结构）、Hierarchy（层级）、Navigation Contract（导航约定）和 Scroll Contract（滚动约定）
继续保持 Frozen。不得通过修改 DOM、组件顺序、Grid / Flex 槽位、路由、Bottom Navigation 或滚动归属来调整本基线。

Final Icon 接入后，只允许通过显式 Optical Alignment Review（视觉光学校正）评审 1～2px 的对齐问题；这不重新开放
整个 Stage 2。任何更大尺寸或比例调整都必须先明确 Unfreeze（解冻）。

## Visual Token Tuner 基线

`src/dev/visual-token-tuner/visual-token-registry.ts` 的 `defaultValue` 必须与本文件和 `tokens.css` 一致。
Visual Token Tuner 的“恢复全部”只移除开发态 Runtime Override 与本机临时记录；恢复后默认值、当前值和 Dirty Count
均应回到正式 Token 基线和 `0`。

`vant-theme.css` 只消费以下语义 Token，没有为本次固化新增第二套 Vant 尺寸常量。

## 最终正式 Token

### Typography（字体排版）

| 角色                   | Token                                               | 正式值      | 主要消费者                             |
| ---------------------- | --------------------------------------------------- | ----------- | -------------------------------------- |
| Caption / Meta         | `--font-size-caption` / `--line-height-caption`     | 11px / 15px | 时间、Meta、Tag、Summary Label         |
| Secondary              | `--font-size-secondary` / `--line-height-secondary` | 12px / 18px | 次级状态、Runtime 辅助内容             |
| Action                 | `--font-size-action` / `--line-height-action`       | 13px / 18px | Button、Selector、Capability Action    |
| Body / Capability Name | `--font-size-body` / `--line-height-body`           | 14px / 20px | 正文、Cell、能力名称                   |
| Section / Card Title   | `--font-size-label` / `--line-height-label`         | 15px / 20px | Toolbar、DeviceCard、TaskCard、Section |
| Brand / Header         | `--font-size-title` / `--line-height-title`         | 16px / 22px | Global Header、Detail Header           |
| Summary Number         | `--font-size-display` / `--line-height-display`     | 18px / 22px | MobileSummaryStrip 数字                |

字重保持 `regular 400`、`medium 500`、`semibold 600`、`bold 700`。业务 Page / Feature 不得建立局部字号或字重体系。

### Spacing（间距）

| 语义                          | Token                                    | 正式值      | 主要消费者                                             |
| ----------------------------- | ---------------------------------------- | ----------- | ------------------------------------------------------ |
| 紧凑内部间距                  | `--space-1`                              | 2px         | Summary、Runtime、Capability、Header / Bottom Nav 细部 |
| 共享内容间距                  | `--space-2`                              | 16px        | DeviceCard / TaskCard 主图标到正文，以及共享内容区域   |
| Page Horizontal / Vertical    | `--layout-page-padding-x / y`            | 16px / 12px | Header、列表、详情页                                   |
| Section Gap                   | `--layout-section-gap`                   | 24px        | Device / Task Detail 一级区块                          |
| Card Gap                      | `--layout-card-gap`                      | 8px         | Device / Task 列表                                     |
| Card Padding X / Y            | `--layout-card-padding-x / y`            | 15px / 16px | DeviceCard、TaskCard                                   |
| Card Row Gap                  | `--layout-card-row-gap`                  | 5px         | 两类业务卡三行正文                                     |
| Summary Padding Y             | `--layout-summary-padding-y`             | 7px         | MobileSummaryStrip                                     |
| Runtime Summary Padding X / Y | `--layout-runtime-summary-padding-x / y` | 17px / 9px  | DeviceRuntimeSummary 上下分区                          |

`--space-1` 与 `--space-2` 是全局语义 Token，改动必须同时审计其全部消费者；不得为了某个页面重新定义
Feature 私有间距 Token。

### Global Dimensions（全局尺寸）

| Token                                | 正式值 | 主要消费者                                |
| ------------------------------------ | ------ | ----------------------------------------- |
| `--layout-header-height`             | 52px   | MobileGlobalHeader                        |
| `--layout-detail-header-height`      | 51px   | MobileDetailHeader、Vant NavBar           |
| `--layout-summary-height`            | 96px   | MobileSummaryStrip                        |
| `--layout-toolbar-height`            | 46px   | MobileListToolbar                         |
| `--layout-bottom-nav-height`         | 58px   | MobileBottomNavigation                    |
| `--touch-target-min`                 | 45px   | 全局可操作入口；仍满足至少 44×44px        |
| `--control-height-compact`           | 26px   | Toolbar / Capability Refresh 的视觉 Shell |
| `--control-size-icon-button`         | 32px   | Theme、Bell、Detail Back 的可见 Shell     |
| `--control-height-capability-action` | 28px   | Configure / Run 的视觉 Shell              |

视觉 Shell 与 Touch Target 是不同职责。不得为了紧凑视觉缩小 45px 操作热区，也不得以扩大的热区改写既有布局结构。

### Card / Icon Ratio（卡片与图标比例）

| 语义                                | Token                                                                      | 正式值      | 主要消费者                          |
| ----------------------------------- | -------------------------------------------------------------------------- | ----------- | ----------------------------------- |
| Primary Leading Visual Slot / Glyph | `--layout-card-leading-icon-slot-width` / `--icon-size-card-leading`       | 52px / 36px | DeviceCard、TaskCard                |
| Chevron Slot / Glyph                | `--layout-card-trailing-icon-slot-width` / `--icon-size-card-chevron`      | 22px / 16px | DeviceCard、TaskCard                |
| Summary Icon                        | `--icon-size-summary-metric`                                               | 16px        | MobileSummaryStrip                  |
| Runtime Slot / Glyph                | `--layout-runtime-summary-icon-slot-width` / `--icon-size-runtime-summary` | 48px / 25px | DeviceRuntimeSummary                |
| Capability Slot / Glyph             | `--layout-capability-icon-slot-width` / `--icon-size-capability-row`       | 36px / 24px | Capability Row                      |
| Control Icon                        | `--icon-size-default`                                                      | 22px        | Header、Bottom Navigation、通用操作 |

Slot（图标槽位）与 Glyph（图形视觉尺寸）始终分离。最终图标资源、Tile、颜色和描边属于 Stage 3，不能通过调整本表的
结构关系提前实现。

### Detail Density（详情密度）

| Token / 规则                         | 正式值                             | 约束                                          |
| ------------------------------------ | ---------------------------------- | --------------------------------------------- |
| `--layout-capability-panel-height`   | 372px                              | Header / Selector 固定，内容区独立滚动        |
| `--layout-capability-row-min-height` | 50px                               | 保持 Configure / Run 的触控约定               |
| Capability Panel Padding X / Y       | 12px / 13px                        | Y 复用 `--space-3 + --border-width`，保证五行 |
| Capability List                      | 前 5 行完整可见；第 6 行起内部滚动 | 不露出半行，不把 Header / Selector 移入滚动区 |
| DeviceRuntimeSummary / Task Detail   | 自然高度                           | 不改 Upper → Separator → Lower 与详情字段层级 |

## 组件定位

- `MobileDetailHeader`：使用 51px 详情头部、45px Touch Target 与 32px 可见图标外壳；不得改变三列对称结构。
- `MobileGlobalHeader`：保持 52px，高度链、Safe Area 和品牌 / Theme / Bell 顺序均冻结。
- `MobileBottomNavigation`：保持 58px、五等分与 Safe Area 所有权；Caption 通过 Vant 映射消费 11px / 15px。
- `MobileSummaryStrip`：保持 96px、7px Y Padding、16px Icon、Icon → Number → Label 和三等分结构。
- `MobileListToolbar`：保持单行工具行结构，46px 高度、26px 可见控件、45px 触控区。
- `DeviceCard` / `TaskCard`：保持三行 Main Content、15px X / 16px Y Padding、5px Row Gap、52px / 36px 主视觉、22px Chevron Slot。
- `DeviceRuntimeSummary`：保持上下两段结构，17px X / 9px Y Padding、48px / 25px 视觉槽位与图标。
- `CapabilityPanel`：保持 372px、X 12px / Y 13px 内边距、50px Row、36px / 24px 图标、前 5 行完整可见和第 6 行起内部滚动。

## Vant 4 映射

统一入口是 `src/shared/styles/vant-theme.css`。本次没有增加业务 Page 的 `:deep()` 尺寸覆盖：

- NavBar 高度映射 `--layout-detail-header-height`（51px）。
- Tabbar Caption 映射 `--font-size-caption / --line-height-caption`（11px / 15px）。
- Tabs、Notice、Calendar、Picker 和可操作项的热区继续映射 `--touch-target-min`（45px）。
- Tag、Search、Cell 与内边距继续通过现有语义 Token 映射，不创建 Vant 私有尺寸基线。

## 后续阶段

Stage 3 仍未冻结：Color、Surface、Radius、Border、Shadow、Final Icons、Dark Visual Hierarchy。

Stage 4 仍未冻结：Press、Motion。

这两个阶段不得改变本文件冻结的 Anatomy、Hierarchy、Navigation Contract、Scroll Contract 或 Stage 2 尺寸基线。

## 验证

每次显式 Review 或 Optical Alignment Review 后，至少运行 Prettier、lint、typecheck、unit、build、Playwright、
Visual Playwright 与 `git diff --check`，并在 360 / 375 / 390 / 430px、Light / Dark 下检查 Safe Area、45px Touch
Target、横向溢出、Console Error 和 Capability 的 5 行 / 第 6 行滚动契约。
