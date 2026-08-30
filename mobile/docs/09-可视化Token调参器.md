# Visual Token Tuner V3（可视化 Token 调参器）

## 用途、加载条件与优先级

Visual Token Tuner 是 `mobile/src/dev/visual-token-tuner/` 中的内部开发工具。它只在
`import.meta.env.DEV` 为真且 `VITE_VISUAL_TUNER !== 'false'` 时加载；Production 不显示入口、不读取
LocalStorage，也不会向根元素或样式表注入任何覆盖。

本工具只帮助观察和临时覆盖已经登记的 Token。项目的 [`AGENTS.md`](../AGENTS.md)、
[`02-设计系统.md`](./02-设计系统.md)、[`08-Stage-2手动微调索引.md`](./08-Stage-2手动微调索引.md)
以及 Frozen Contract（冻结契约）优先级更高。调参器不能修改 DOM、路由、导航、滚动约定、业务 Contract、
API、DTO、Store 或 Query。

Stage 1 Anatomy / Hierarchy / Navigation / Scroll Contract 与 Stage 2 Geometry 均 Frozen，唯有已记录的
Card / Icon Ratio Scoped Unfreeze（共享 Primary Leading Visual `72 / 56px` 候选）例外；Stage 3A 的
Light / Dark Semantic Color Token 也全部 Frozen。V3 的外观通道只能调 Radius、可见 Border Width / Presence
与 Shadow 参数；不得调 Color、Surface、Typography、Spacing、Height、Width、Padding、Gap、Icon、Control Size、
Touch Target、Press、Motion、Gradient、Glass 或 Final Icon。

## V3 的三通道能力

V3 保留 V2 的尺寸与颜色通道，并增加互相隔离的“外观”通道：

| 通道 | 分组                                                            | 可调内容                                                                                                          | 不可调内容                                              |
| ---- | --------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| 尺寸 | Card、Summary、Runtime、Capability、Global、Control、Typography | Stage 2 已登记的语义尺寸 Token                                                                                    | 原子 `--space-*`、结构、路由、滚动与未登记尺寸          |
| 颜色 | Surface、Text、Status、Selected                                 | 已登记的 Light / Dark Semantic Color Token                                                                        | PC Token、Page 私有颜色、Gradient、Shadow、Final Icon   |
| 外观 | Radius、Border、Shadow                                          | Card / Panel / Control / Tag / Popup Radius；可见内描边宽度；Card / Raised / Popup 的 X、Y、Blur、Spread、Opacity | Color、Surface、物理 Box Model、Press、Motion、最终图标 |

Tuner 顶部始终显示“尺寸已调整 / 颜色已调整 / 外观已调整”的 Dirty Count（已修改数量），让用户知道哪些值
仍只是本地开发态临时值。Radius 与可见 Border 为共用 Token；Shadow 通过“编辑浅色阴影 / 编辑深色阴影”切换，
不会改变产品 Theme Store。

### 外观语义与范围

| 外观组 | 语义 Token                                                                                                    | 影响范围                                                                   |
| ------ | ------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Radius | `--radius-card`、`--radius-panel`、`--radius-control`、`--radius-tag`、`--radius-overlay`                     | Card、Panel、紧凑 Control、Tag、Popup / Sheet / Dialog                     |
| Border | `--appearance-border-surface-width`、`--appearance-border-control-width`、`--appearance-border-overlay-width` | 通过 inset visual border 控制可见边界，不改变 Stage 2 的物理 1px Box Model |
| Shadow | `--shadow-card-*`、`--shadow-raised-*`、`--shadow-overlay-*`                                                  | Light / Dark 独立的 Content Card、Raised Icon Control、Popup / Sheet 层级  |

Shadow Color 不开放任意输入；它继续使用 `tokens.css` 内的中性色组合，从而不会触碰 Stage 3A Frozen 的 Surface、
Border Color、Text 或 Status。Capability Row、Toolbar、Header、Bottom Navigation Item 与普通 Tag 不因 Tuner
获得私有 Shadow。

## 如何开启与调节

1. 在 `mobile` 目录运行 `pnpm dev` 或 `pnpm dev:visual`。
2. 真实预览页右下角出现小型“调参”入口；点击后在独立 `/#/__visual-tuner` 开发窗口打开，预览页不会被 Sheet
   或 Popup 遮挡。
3. 选择“尺寸 / 颜色 / 外观”。外观通道可选择“圆角 / 边界 / 阴影”；阴影额外选择浅色或深色编辑上下文。
4. Slider、数值输入或颜色输入立即修改开发态 Runtime Override，并通过 LocalStorage 事件同步到已打开的真实
   Device / Task 预览页；无需点击保存或刷新页面。
5. 关闭独立窗口不会清除临时值。要提交正式值，必须由 Codex 回写 `tokens.css`、相关 Mapping、Registry 默认值、
   文档和测试后再清除 Override。

调 Radius / Border 后，应确认 DeviceCard / TaskCard、MobileSummaryStrip、DeviceRuntimeSummary、CapabilityPanel、
Selector / Filter、Tag 与 Popup / Sheet 只改变外观而不改变高度、Padding、Gap、Touch Target 或滚动。调 Shadow 后，
至少在 390px Light / Dark 的 Device List、Device Detail、Task List、Task Detail 观察 Surface 层级；不得借重阴影
制造 Card 海、发光、灰边或 Neumorphism。

## 临时保存、隔离与恢复

V1/V2 与 V3 使用不同 LocalStorage Key，避免跨阶段污染：

| 阶段          | Key                                           | 数据                                                                   |
| ------------- | --------------------------------------------- | ---------------------------------------------------------------------- |
| V1 / V2       | `control-center.mobile.visual-token-tuner-v1` | `version: 2`，`dimensions` + 按 Light / Dark 分组的 `colors`           |
| V3 Appearance | `control-center.mobile.visual-token-tuner-v3` | `version: 3`，共用 `common`（Radius / Border）+ 按主题分组的 `shadows` |

V3 Runtime CSS 使用独立 `<style>` 节点；Shadow Override 以 `:root[data-theme='light']` 与
`:root[data-theme='dark']` 分别注入。因此浅色 Shadow 不污染深色，反之亦然；Radius 与 Border 仍只维护一份。
旧 V1/V2 数据不能被 V3 读取、升级或写入。

恢复行为固定如下：

- **恢复单项**：只删除当前一个 Stage 2 / 3A / 3B 临时项。
- **恢复本组**：恢复当前尺寸组、当前颜色主题或当前外观组；Shadow 只恢复当前编辑主题。
- **恢复 Stage 3B**：只删除 V3 的 Radius / Border / Shadow Override，不触碰 V2 尺寸或颜色 Override。
- **恢复全部调参**：清除所有三个开发态 Override 通道；它仍只清理 LocalStorage / Runtime CSS，绝不改写
  Stage 1、Stage 2、Stage 3A 或正式 `tokens.css` 的基线。

在刷新后，仍存在的 Development Override 会恢复；值等于已加载 `tokens.css` 基线时会自动清理，确保 Dirty Count
回到 `0`。Production Build 不会初始化任一 Runtime、读取 LocalStorage 或显示调参入口。

## 导出与正式固化

“复制尺寸 CSS / JSON”“复制颜色 CSS / JSON”和“复制外观 CSS / JSON”分别只导出所在通道。外观导出包含共用
Radius / Border 与按 Light / Dark 分组的 Shadow，不混入无关的尺寸或颜色。

浏览器不会写入 `tokens.css`。正式采用任何值必须遵循：

```text
实时调节并人工确认
↓
复制对应通道 CSS 或 JSON
↓
由 Codex 同步 tokens.css、Vant / Shared Mapping、Registry defaultValue 与文档
↓
清除对应 Runtime Override
↓
按 04-开发验证规范执行验证、Review 与 Commit
```

本次 Stage 状态为：Stage 1 Frozen、Stage 2 除 Card / Icon Ratio Scoped Unfreeze 外 Frozen、Stage 3A Frozen、Stage 3B
**Completed / Frozen（已完成 / 已冻结）**；Stage 3C Final Icons 处于独立的 Candidate for Visual Review（候选人工
视觉复核），不属于 Tuner V3 的可调通道。Tuner V3 的默认值已经与 `tokens.css` 的 Stage 3B 正式基线同步；打开调参器时，
外观当前值等于默认值且 Dirty Count 为 0，Reset Stage 3B 也只回到这组正式值。后续若需要改变 Radius、Border 或 Shadow，
必须先显式 Unfreeze（解冻）并完成新的视觉 Review；不得顺手开始 Stage 4 Press / Motion。

## 视觉验收

每次显式外观 Review 至少检查 360 / 375 / 390 / 430px、Light / Dark、Safe Area、45px Touch Target、Console Error、
Horizontal Overflow 与 Capability 完整 5 行 / 第 6 行内部滚动。重点人工基准为 390 × 844 的 Device List、Device
Detail、Task List、Task Detail；Before / Frozen Baseline 截图只能作为非提交的审查证据，不能覆盖已冻结的 Stage 2 /
3A 基线证据。
