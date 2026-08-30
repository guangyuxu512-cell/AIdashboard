# Stage 2 手动微调索引

> `/devices` 已进入 Mobile Visual V2 选择性迁移，旧 Device V1 的 Summary、Toolbar、Card 与 Primary
> Leading Visual 数值不再约束该列表页；它们仍约束未迁移的 TaskCard、详情和其它既有组件。Visual V2
> 当前共享基础范围已完成 Freeze Audit 并 Frozen，完整覆盖条款见
> [`10-Mobile-Visual-V2-设备列表.md`](./10-Mobile-Visual-V2-设备列表.md)。禁止用本索引旧值回写 Visual V2。

本文记录 Mobile Stage 2 的唯一正式尺寸基线。正式值以
`src/shared/styles/tokens.css` 为权威来源；本文件用于说明 Token 的职责、消费者与冻结边界，不能创建
第二套值。

## 状态与冻结范围

Status（状态）: **Completed / Candidate for Visual Review（已完成 / 候选人工视觉复核）**

本次基线来自已完成的 Visual Token Tuner V1 人工微调，并在 V2 中保持同一套尺寸默认值。冻结范围为：

- Typography（字体排版）
- Spacing（间距）
- Global Dimensions（全局尺寸）
- Card / Icon Ratio（卡片与图标比例，当前仅此项经显式 Scoped Unfreeze 解冻）
- Controls（控件尺寸）
- Detail Density（详情密度）

Stage 1 的 Anatomy（结构）、Hierarchy（层级）、Navigation Contract（导航约定）和 Scroll Contract（滚动约定）
继续保持 Frozen。不得通过修改 DOM、组件顺序、Grid / Flex 槽位、路由、Bottom Navigation 或滚动归属来调整本基线。

除本次明确记录的 Card / Icon Ratio 复核外，Final Icon 接入后仍只允许通过显式 Optical Alignment Review（视觉光学校正）
评审 1～2px 的对齐问题；任何更大尺寸或比例调整都必须先明确 Unfreeze（解冻）。

## Scoped Unfreeze：Card / Icon Ratio

用户在透明显示器 PNG 接入后的真实 Device List 审查中，明确要求放大主视觉占比。解冻范围仅为
`--layout-card-leading-icon-slot-width` 与 `--icon-size-card-leading`：当前候选为 `72px / 56px`，用于
DeviceCard 与 TaskCard 共享的 Primary Leading Visual。调参器的对应上限同步扩展为 `80px / 64px`。

不解冻 Card Padding、Card Gap、Row Gap、Leading / Content Gap、三行正文、Trailing Chevron、Header、Navigation、
Scroll Contract、Theme 或任意 Stage 3A / 3B Token。候选值必须完成新的人工视觉确认后才能重新标记为 Frozen。

## Visual Token Tuner 基线

`src/dev/visual-token-tuner/visual-token-registry.ts` 的 `defaultValue` 必须与本文件和 `tokens.css` 一致。
Visual Token Tuner V2 的“恢复全部尺寸”只移除开发态的尺寸 Runtime Override；颜色恢复具有独立入口，不能清除
Stage 2 尺寸记录。尺寸恢复后默认值、当前值和尺寸 Dirty Count 均应回到正式 Token 基线和 `0`。

`vant-theme.css` 只消费下列稳定语义 Token 或独立的原子刻度映射，没有为本次固化新增第二套 Vant 尺寸常量。

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

| 语义                          | Token                                                       | 正式值                                | 主要消费者                              |
| ----------------------------- | ----------------------------------------------------------- | ------------------------------------- | --------------------------------------- |
| 原子间距刻度                  | `--space-1` ～ `--space-8`                                  | 4 / 8 / 12 / 16 / 20 / 24 / 28 / 32px | 比例尺；不作为业务组件或调参器局部入口  |
| 紧凑通用间距                  | `--layout-compact-gap`                                      | 2px                                   | Header、Tag、轻量状态等非特定紧凑关系   |
| 标准内容间距                  | `--layout-content-gap`                                      | 16px                                  | Vant 基础映射、通用列表与非特定内容区域 |
| Card Leading / Content Gap    | `--layout-card-leading-content-gap`                         | 16px                                  | DeviceCard、TaskCard 主视觉到正文       |
| Summary Metric Gap / Padding  | `--layout-summary-metric-gap / -padding-x`                  | 2px / 16px                            | MobileSummaryStrip 三层 Metric          |
| Toolbar Group / Inner Gap     | `--layout-toolbar-group-gap / -inner-gap`                   | 16px / 2px                            | MobileListToolbar 左右组与组内元素      |
| Runtime Leading / Inner Gap   | `--layout-runtime-summary-leading-content-gap / -inner-gap` | 16px / 2px                            | DeviceRuntimeSummary 图标与内容、内部行 |
| Capability Panel / Row Gap    | `--layout-capability-panel-gap / -row-gap`                  | 2px / 16px                            | CapabilityPanel 区块与 Capability Row   |
| Page Horizontal / Vertical    | `--layout-page-padding-x / y`                               | 16px / 12px                           | Header、列表、详情页                    |
| Section Gap                   | `--layout-section-gap`                                      | 24px                                  | Device / Task Detail 一级区块           |
| Card Gap                      | `--layout-card-gap`                                         | 8px                                   | Device / Task 列表                      |
| Card Padding X / Y            | `--layout-card-padding-x / y`                               | 15px / 16px                           | DeviceCard、TaskCard                    |
| Card Row Gap                  | `--layout-card-row-gap`                                     | 5px                                   | 两类业务卡三行正文                      |
| Summary Padding Y             | `--layout-summary-padding-y`                                | 7px                                   | MobileSummaryStrip                      |
| Runtime Summary Padding X / Y | `--layout-runtime-summary-padding-x / y`                    | 17px / 9px                            | DeviceRuntimeSummary 上下分区           |

原子刻度不直接承载业务语义，也不在 Visual Token Tuner 中作为单个组件的调参项。调参器只暴露 Card、
Summary、Runtime、Capability 等稳定语义 Token；旧的 `--space-1` / `--space-2` LocalStorage 覆盖会被安全
忽略并清理，不能重新注入页面。不得为了某个页面重新定义 Feature 私有间距 Token。

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
| Primary Leading Visual Slot / Glyph | `--layout-card-leading-icon-slot-width` / `--icon-size-card-leading`       | 72px / 56px | DeviceCard、TaskCard                |
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
- `DeviceCard` / `TaskCard`：保持三行 Main Content、15px X / 16px Y Padding、5px Row Gap、72px / 56px 候选主视觉、22px Chevron Slot。
- `DeviceRuntimeSummary`：保持上下两段结构，17px X / 9px Y Padding、48px / 25px 视觉槽位与图标。
- `CapabilityPanel`：保持 372px、X 12px / Y 13px 内边距、50px Row、36px / 24px 图标、前 5 行完整可见和第 6 行起内部滚动。

## Vant 4 映射

统一入口是 `src/shared/styles/vant-theme.css`。本次没有增加业务 Page 的 `:deep()` 尺寸覆盖：

- NavBar 高度映射 `--layout-detail-header-height`（51px）。
- Tabbar Caption 映射 `--font-size-caption / --line-height-caption`（11px / 15px）。
- Tabs、Notice、Calendar、Picker 和可操作项的热区继续映射 `--touch-target-min`（45px）。
- Tag、Search、Cell 与内边距继续通过现有语义 Token 映射，不创建 Vant 私有尺寸基线。

## 后续阶段

Stage 3A 的 Color、Surface、Text、Status、Selected 与 Dark Hierarchy 已完成并 Frozen；任何后续颜色改动都必须先
显式 Unfreeze（解冻）并完成视觉 Review。Stage 3B 已冻结 Radius、Border Presence / Visual Width 与 Light / Dark
Shadow 正式体系，当前状态为 **Completed / Frozen（已完成 / 已冻结）**；它绝不重新开放本索引的尺寸基线。Stage 3C
Final Icons 当前处于 **Candidate for Visual Review（候选人工视觉复核）**，只能替换图标资源与语义入口；Stage 4
Press / Motion 仍留给后续显式 Review。

## Stage 3A 几何复核记录

Stage 3A 开始前、候选色彩映射落地后与最终颜色冻结时，均以 `390 × 844` Light 的真实浏览器页面读取冻结几何。结果为 `0` 尺寸
差异：Global Header `52px`、Detail Header `51px`、Summary `96px`、Toolbar `46px`、Bottom Navigation
`58px`；当时 DeviceCard / TaskCard 为 `15px X / 16px Y` Padding、`52 / 36px` Primary Leading Visual。该记录已被
本次显式 Scoped Unfreeze 的 `72 / 56px` 候选替代；其余 Card Padding、Leading / Content Gap、Runtime
`17 / 9px` 与 Capability Panel / Row `372px / 50px` 保持不变，
完整 5 行且第 6 行才在内部滚动。360px 与 430px Light、390px Dark 的自动化检查同样没有横向溢出或 Touch
Target 回退。

Stage 4 仍未冻结：Press、Motion。

这两个阶段不得改变本文件冻结的 Anatomy、Hierarchy、Navigation Contract、Scroll Contract 或 Stage 2 尺寸基线。

## Mobile Visual V2 Selective Override（选择性覆盖）

`/devices` 已通过显式 Selective Unfreeze 进入 Visual V2。以下值是 Device List 与共享 V2 Pattern 的正式冻结
覆盖，不改写本文件中未迁移 V1 页面历史：Page Header 66px、Search 44px、Metric Strip 90px、DeviceCard
最小 122px / Gap 14px / Grid 102px + `minmax(0, 1fr)` + 18px、Artwork 80×80px、Bottom Navigation
64px 主体 / 25px Icon / 12px Label。Global Font Family 与 `--typography-v2-*` 也只在迁移组件中消费；
未迁移 Task、Detail、Schedule、Shop、Me 继续保持 V1 Frozen Geometry。

Visual V2 的完整 Token、共享 Foundation 状态与三态 Device 规则见
[`02-设计系统.md`](./02-设计系统.md) 和
[`10-Mobile-Visual-V2-设备列表.md`](./10-Mobile-Visual-V2-设备列表.md)。当前审计范围状态是
**Completed / Frozen**；`MobileListToolbar V2` 因 `/devices` 未实际使用，仍为 Shared Candidate。

## 验证

每次显式 Review 或 Optical Alignment Review 后，至少运行 Prettier、lint、typecheck、unit、build、Playwright、
Visual Playwright 与 `git diff --check`，并在 360 / 375 / 390 / 430px、Light / Dark 下检查 Safe Area、45px Touch
Target、横向溢出、Console Error 和 Capability 的 5 行 / 第 6 行滚动契约。
