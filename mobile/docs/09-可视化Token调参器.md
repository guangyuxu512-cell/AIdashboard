# Visual Token Tuner V1（可视化 Token 调参器）

## 用途与边界

Visual Token Tuner 是 `mobile/src/dev/visual-token-tuner/` 中的内部开发工具。它只在
`import.meta.env.DEV` 为真且 `VITE_VISUAL_TUNER !== 'false'` 时加载；Production 不显示入口、
不读取 LocalStorage，也不会向根元素注入 CSS Variable 覆盖。

它只允许临时覆盖已登记的 Stage 2 尺寸、**语义间距**、图标容量、控件和 Typography Token。原子间距刻度
`--space-*` 不会作为调参输入暴露。工具不能调整
颜色、Surface、Radius、Shadow、最终图标、Press、Motion，也不能调整 DOM、路由、导航或滚动约定。
Stage 1 Frozen Contract 与 Stage 2 Final Frozen Baseline 仍以
[`02-设计系统.md`](./02-设计系统.md) 和
[`08-Stage-2手动微调索引.md`](./08-Stage-2手动微调索引.md) 为准。

## 如何开启与调节

1. 在 `mobile` 目录运行 `pnpm dev` 或 `pnpm dev:visual`。
2. 正式预览页右下角出现小型“调参”入口；点击后打开独立的 `/#/__visual-tuner` 开发窗口，预览页不会被
   Sheet 或 Popup 遮挡。
3. 独立窗口不渲染产品 Header、Bottom Navigation 或业务页面；它只承载卡片、概览、运行摘要、能力、全局布局、
   控件与字体分组。
4. Slider 和数值输入会在 `input` 时立刻修改独立窗口的根 CSS Variable，并通过开发态 LocalStorage 事件同步到
   已打开的真实预览页面。预览页无需刷新。
5. 关闭独立窗口不会清除当前临时值；可继续完整查看预览页。

面板会读取浏览器当前的 Computed CSS Variable 值，而不是只显示 Registry 默认值；顶部显示当前
Viewport 和“已调整”数量。低于 44px 的 Touch Target 会给出提醒。修改 Capability Row 或 Panel Height
后，必须人工确认仍完整显示 5 行且第 6 行才开始内部滚动。

## 临时保存、恢复与正式落盘

开发态临时值只保存到浏览器 LocalStorage：
`control-center.mobile.visual-token-tuner-v1`。开发启动时会自动恢复；已打开的预览页和独立调参窗口会监听
同一存储记录，因此单项“恢复”与“恢复全部”也会立即同步回预览页。“恢复全部”会移除本工具登记的全部覆盖和
该存储记录。历史版本保存在同一记录中的 `--space-1` / `--space-2` 覆盖会被安全忽略并清理，不会重新注入页面。

“复制 CSS”输出完整的 `:root { --token: value; }` 片段，“复制 JSON”输出同一组 Token 的当前值。浏览器
不会写入 `tokens.css`。需要正式采用的数值应按以下流程处理：

```text
实时调节并人工确认
↓
复制 CSS / JSON
↓
由 Codex 修改 mobile/src/shared/styles/tokens.css
↓
按 04-开发验证规范执行验证、Review 与 Commit
```

正式固化后必须同步更新 `tokens.css` 与 Visual Token Registry 的 `defaultValue`，再使用“恢复全部”清除
临时覆盖。重新打开调参器时，默认值与当前值必须等于正式 Token，Dirty Count 必须为 `0`。

调参器本身不替代页面级视觉验收；仍需在 360 / 375 / 390 / 430px、Light / Dark 下检查 Safe Area、
触控、横向溢出、Capability 内部滚动和 Frozen Contract。
