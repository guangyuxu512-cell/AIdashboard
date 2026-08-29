# Visual Token Tuner V2（可视化 Token 调参器）

## 用途、加载条件与优先级

Visual Token Tuner 是 `mobile/src/dev/visual-token-tuner/` 中的内部开发工具。它只在
`import.meta.env.DEV` 为真且 `VITE_VISUAL_TUNER !== 'false'` 时加载；Production 不显示入口、不读取
LocalStorage，也不会向根元素或样式表注入任何覆盖。

本工具只帮助观察和临时覆盖已经登记的 Token。项目的 [`AGENTS.md`](../AGENTS.md)、
[`02-设计系统.md`](./02-设计系统.md)、[`08-Stage-2手动微调索引.md`](./08-Stage-2手动微调索引.md)
以及 Frozen Contract（冻结契约）优先级更高。调参器不能修改 DOM、路由、导航、滚动约定、业务 Contract、
Radius、Border Width / Style、Shadow、最终 Icon、Press 或 Motion。

## V2 的双通道能力

V2 在 V1 的尺寸调节基础上增量增加颜色调节：

| 通道 | 分组                                                            | 可调内容                                                | 不可调内容                                            |
| ---- | --------------------------------------------------------------- | ------------------------------------------------------- | ----------------------------------------------------- |
| 尺寸 | Card、Summary、Runtime、Capability、Global、Control、Typography | Stage 2 已登记的语义尺寸 Token                          | 原子 `--space-*`、结构、路由、滚动、Stage 2 未登记值  |
| 颜色 | 颜色与表面、文字、状态、选中                                    | `tokens.css` 中登记的 Light / Dark Semantic Color Token | PC Token、Page 私有颜色、Gradient、Shadow、Final Icon |

“尺寸”和“颜色”的 Dirty Count（已修改数量）分开显示。尺寸“恢复全部尺寸”仅清除尺寸 Runtime Override；
颜色“恢复本主题 / 恢复全部颜色”仅清除颜色 Override。因此 Stage 3A 的颜色试验不会抹掉已有的 Stage 2 尺寸试验，
反之亦然。

颜色 Registry 只保存中文语义、主题、说明与对比度目标；每个颜色项的“默认”值由运行时从已加载的
`tokens.css` 读取。它不会在 Registry 再维护一份 Hex，确保 `tokens.css` 是 Mobile 颜色唯一事实来源。
一套语义模板会按 Light / Dark 生成条目，避免维护两段重复的主题 Registry。

## Light / Dark 编辑上下文

颜色页提供“编辑浅色 / 编辑深色”。这个选择只决定当前正在编辑哪一套 Token，不调用 Theme Store，也不改变用户
正在预览的 App Theme。可在真实预览页使用正式 Theme Action 切换 Light / Dark，以确认每套覆盖的实际效果。

颜色 Runtime Override 以主题隔离方式注入：

```css
:root[data-theme='light'] {
  --bg-app: #f4f6f8;
}

:root[data-theme='dark'] {
  --bg-app: #101820;
}
```

因此同一 Token 在 Light 与 Dark 可以同时拥有不同的临时值，切换 App Theme 时不会串色。V2 的颜色输入只接受
`#RRGGBB`；每项提供颜色选择器、HEX 输入、单项恢复、默认值和当前值。文本与状态前景会在已登记的目标 Surface
上给出简单的对比度提醒，提醒用于开发期筛查，不替代真实页面的 Light / Dark 人工验收。

## 如何开启与调节

1. 在 `mobile` 目录运行 `pnpm dev` 或 `pnpm dev:visual`。
2. 正式预览页右下角出现小型“调参”入口；点击后打开独立的 `/#/__visual-tuner` 开发窗口，预览页不会被 Sheet 或
   Popup 遮挡。
3. 独立窗口不渲染产品 Header、Bottom Navigation 或业务页面；它只承载 Token 调节界面。先选“尺寸”或“颜色”，
   再选择具体分组；颜色通道额外选择 Light / Dark 编辑上下文。
4. Slider、数值输入或颜色输入会立即修改开发态 Runtime Override，并通过 LocalStorage 事件同步到已打开的真实预览页。
   预览页无需刷新。
5. 关闭独立窗口不会清除当前临时值；可继续完整查看 Device / Task 真实预览页。

修改 Capability Row 或 Panel Height 后，必须人工确认仍完整显示 5 行且第 6 行才开始内部滚动。修改颜色后，至少在
390px Light / Dark 的 Device List、Device Detail、Task List 与 Task Detail 中检查 Surface 层级、Text、Status、
Header、Bottom Navigation 与无横向溢出。

## 临时保存、恢复与正式落盘

开发态临时值只保存到浏览器 LocalStorage：`control-center.mobile.visual-token-tuner-v1`。V2 的记录结构为：

```json
{
  "version": 2,
  "dimensions": { "--layout-card-padding-y": "16px" },
  "colors": {
    "light": { "--bg-app": "#f4f6f8" },
    "dark": { "--bg-app": "#101820" }
  }
}
```

旧 V1 的扁平尺寸记录仍可读取，并会在下一次有效保存时升级为 V2；历史 `--space-1` / `--space-2` 覆盖会继续被安全
忽略和清理，不能重新注入页面。颜色“复制 CSS”输出独立的 Light / Dark 选择器；“复制 JSON”输出分主题对象，
不会混成一套无主题颜色。

浏览器不会写入 `tokens.css`。需要正式采用的值，遵循：

```text
实时调节并人工确认
↓
复制尺寸 / 颜色 CSS 或 JSON
↓
由 Codex 同步 tokens.css、尺寸 Registry defaultValue、颜色 Registry 的语义登记与相关文档
↓
清除对应 Runtime Override
↓
按 04-开发验证规范执行验证、Review 与 Commit
```

正式固化后，重新打开调参器时，尺寸和颜色的默认值与当前值都必须等于正式 Token，对应 Dirty Count 必须为 `0`。
调参器不替代页面级视觉验收；仍需在 360 / 375 / 390 / 430px、Light / Dark 下检查 Safe Area、45px Touch
Target、横向溢出、Capability 内部滚动和 Frozen Contract。

Stage 3A 的颜色基线现已 Frozen（已冻结）：Tuner V2 继续作为开发期评审工具，但任何正式颜色变更都必须先显式
Unfreeze（解冻）并重新完成页面级视觉验收。
