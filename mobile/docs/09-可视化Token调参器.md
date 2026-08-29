# Visual Token Tuner V1（可视化 Token 调参器）

## 用途与边界

Visual Token Tuner 是 `mobile/src/dev/visual-token-tuner/` 中的内部开发工具。它只在
`import.meta.env.DEV` 为真且 `VITE_VISUAL_TUNER !== 'false'` 时加载；Production 不显示入口、
不读取 LocalStorage，也不会向根元素注入 CSS Variable 覆盖。

它只允许临时覆盖已登记的 Stage 2 尺寸、间距、图标容量、控件和 Typography Token。工具不能调整
颜色、Surface、Radius、Shadow、最终图标、Press、Motion，也不能调整 DOM、路由、导航或滚动约定。
Stage 1 Frozen Contract 与 Stage 2 Candidate Baseline 仍以
[`02-设计系统.md`](./02-设计系统.md) 和
[`08-Stage-2手动微调索引.md`](./08-Stage-2手动微调索引.md) 为准。

## 如何开启与调节

1. 在 `mobile` 目录运行 `pnpm dev` 或 `pnpm dev:visual`。
2. 页面右下角出现小型“调参”入口；点击后，宽屏显示右侧面板，窄屏显示底部调参面板。
3. 选择卡片、概览、运行摘要、能力、全局布局、控件或字体分组；Slider 和数值输入会在 `input` 时立刻
   修改当前真实页面的根 CSS Variable。
4. 关闭面板即可无遮挡查看真实页面；关闭不会清除当前临时值。

面板会读取浏览器当前的 Computed CSS Variable 值，而不是只显示 Registry 默认值；顶部显示当前
Viewport 和“已调整”数量。低于 44px 的 Touch Target 会给出提醒。修改 Capability Row 或 Panel Height
后，必须人工确认仍完整显示 5 行且第 6 行才开始内部滚动。

## 临时保存、恢复与正式落盘

开发态临时值只保存到浏览器 LocalStorage：
`control-center.mobile.visual-token-tuner-v1`。开发启动时会自动恢复；单项“恢复”会移除该项覆盖，
“恢复全部”会移除本工具登记的全部覆盖和该存储记录。

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

调参器本身不替代页面级视觉验收；仍需在 360 / 375 / 390 / 430px、Light / Dark 下检查 Safe Area、
触控、横向溢出、Capability 内部滚动和 Frozen Contract。
