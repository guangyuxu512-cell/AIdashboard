# 视觉布局与 Design Token

## 原则

所有页面共享统一视觉基线。
禁止单页自行定义一套字体、间距、圆角、颜色和阴影。

## Design System V2 基线

```text
Sidebar width: 228px
Topbar height: 54px
Page horizontal padding: 20px
Page vertical padding: 16px
Section gap: 14px
Card gap: 12px

Page title: 18px / 600
Section title: 16px / 600
Body: 14px / 400
Secondary: 13px / 400
Selected navigation: 14px / 500
Font: Segoe UI / Microsoft YaHei / PingFang SC / system-ui
Body / compact line-height: 1.5 / 1.35

Control height: 34px
Card radius: 9px
Dialog radius: 10px
Table header / row: 38px / 42px
```

实际项目以 `tokens.css` 为唯一权威。

建议：

```text
shared/styles/
├── tokens.css
├── typography.css
├── layout.css
└── theme.css
```

优先语义 Token：

- text-primary
- text-secondary
- bg-page
- bg-card
- border-default
- primary
- success
- warning
- error

禁止业务页面散落十六进制颜色。

Naive UI 统一通过 Theme Override 对接 Token。
页面统一使用 AppShell、PageHeader、PageSection。

AppShell 默认品牌为“思余AI中控台”。品牌图使用真实 Alpha 透明资产，不携带 Light/Dark 固定
底板；图像只叠加在 `--bg-sidebar` 上，因此 Light、Dark 与 System 共享同一轮廓并自然跟随主题。
业务页面不得为品牌图另加不受 Token 控制的背景色。

## 阶段 0B 已建立 Token

权威文件：`frontend/src/shared/styles/tokens.css`。

| 类别      | Token                                                                                         |
| --------- | --------------------------------------------------------------------------------------------- |
| 品牌/状态 | `--color-primary*`、`--color-info*`、`--color-success*`、`--color-warning*`、`--color-error*` |
| 文本/表面 | `--color-text-*`、`--color-bg-*`、`--color-border-*`                                          |
| 排版      | `--font-family-base`、`--font-size-*`、`--font-weight-*`、`--line-height-*`                   |
| 间距      | `--space-1` 至 `--space-8`                                                                    |
| 控件      | `--control-height-*`、`--field-width-*`、`--date-picker-width-*`                              |
| 圆角/阴影 | `--radius-*`、`--shadow-*`                                                                    |
| 弹层      | `--dialog-width-*`、`--drawer-width-*`                                                        |
| 布局      | `--layout-*`、`--table-header-height`、`--table-row-height`、`--table-list-viewport-height`    |

`typography.css` 只负责全局排版基线，`layout.css` 只负责页面和语义宽度布局，`theme.css` 是应用唯一样式入口。Naive UI 的全局覆盖位于 `app/providers/naive-theme.ts`，其尺寸直接引用 CSS Token；需要参与 Naive 颜色计算的值必须在 Provider 创建时从 CSS Token 读取计算值，禁止在 TypeScript 再复制一份颜色常量。

`--table-list-viewport-height` 是标准 10 行管理列表的稳定视口高度，由表头、包含标准操作控件的行槽、每页数量和分隔线 Token 推导。`--table-row-height` 仍表达普通文本行密度，`--table-list-row-slot-height` 表达列表操作行的实际占位。业务页面不得复制计算式或另写像素高度；空态、单行和满页状态均复用该语义 Token，Pagination 因而保持在稳定位置。

## 阶段 2C 主题与语义 Token

Theme Store 支持 `graphite`（石墨浅色，默认）、`forest`（森林绿）、`coral`（珊瑚红）、`midnight`（午夜青）与 `system`。沿用 Renderer `localStorage` 的 `control-center.theme-mode` 键；旧 `light` / `dark` 分别映射 graphite / midnight。跟随系统解析到 graphite / midnight，不是第五套配色。根节点保留 `data-theme=light|dark`，另以 `data-theme-preset` 区分预设。Electron 仍只通过类型化 `window.desktop.appearance.setTitleBarTheme` 接收实际 Light / Dark 结果；Web 无 Electron 依赖。

四套共用尺寸、间距、字体与密度。CSS Token 是配色唯一来源；Naive Provider 和 ECharts 必须依赖 `resolvedPreset`，确保浅色之间切换也更新控件、弹出层及图表。切换不重新挂载页面、不清空草稿或筛选、不触发业务动作。

`--text-link` 表达交互文字，`--text-on-primary` 表达主按钮及复选框前景；`--text-inverse` 保留旧语义。侧栏文字、图标、箭头与分割线消费 `--sidebar-*`，不使用浅色内容正文色。`--chart-primary` 是图表主线，面积透明度为 8%；网格、坐标和 Tooltip 复用边框、辅助文字及内容表面。平台 Logo、商品图片和 Mock 图片内容保留原色。

Token 分层：

```text
Base Token
├── Typography / Spacing / Density / Radius / Layout
└── Four presets → Light / Dark Semantic Token
    ├── Accent
    ├── Text
    ├── Surface
    ├── Border / Shadow
    └── Status
```

新的全局实现应优先使用 `--text-*`、`--bg-*`、`--border-*`、`--status-*` 语义 Token。`--color-text-*`、`--color-bg-*` 等旧名称仅作兼容别名，不得在业务页新增随机颜色。

视觉辨识度调整只能收敛到既有语义 Token 与 Naive UI 全局覆盖：`--border-subtle` 用于可见的层级分隔，`--border-default` 用于可操作控件边界，`--color-primary-soft` 与 `--color-primary` 共同表达选中状态。禁用控件必须继续使用 `--bg-subtle` 和 `--text-disabled`，与正常控件明确区分；业务页面不得自行覆写这些状态色。

## 全局表面

### 四套主题返修落点

| 预设 | 侧栏 | 页面 | 卡片 | 主按钮 | 辅助色 |
| --- | --- | --- | --- | --- | --- |
| 石墨浅色 | `#1F2937` | `#F3F4F6` | `#FFFFFF` | `#2563EB` | `#64748B` |
| 森林绿 | `#123E3B` | `#F8FBF5` | `#FFFFFF` | `#2F6F45` | 薄荷 `#DDF7E3`、青柠 `#B7E44B` |
| 珊瑚红 | `#D52E3B` | `#FFF9F5` | `#FFFFFF` | `#D52E3B` | 暖橙 `#F4A261`、浅珊瑚 `#FFB4A2`；图表强调 `#E63946` |
| 午夜青 | `#0B1E3F` | `#111827` | `#1F2937` | `#12A08F` | 青绿 `#2DD4BF`、少量暖橙 `#F59E0B` |

森林薄荷用于表头/轻层次与选中表面，青柠只用于小面积导航标识；珊瑚侧栏用白色文字与深红选中背景，不把成功/警告语义改红。午夜内容表面采用中性灰明度分层，不延续全蓝工具栏/表头。颜色仍只由 CSS Token 定义，不在页面复制。

Sidebar、Topbar、Surface/Card 与弹层使用纯色和必要的轻阴影，不使用玻璃模糊或大面积渐变。兼容 `--glass-blur` 保留为 0px。普通文字（含辅助、占位、交互文字及按钮各可操作状态）目标对比度至少 4.5:1；禁用态单独检查辨识度，不与可操作状态混淆。中性基础色约 85%、辅助色约 10%、主色约 5% 用于控制视觉份量，不进行像素计数或改变布局凑比例。

移除 `backdrop-filter` 时，以 `isolation: isolate` 保留原 Surface 的层叠边界，避免 DataTable 固定列/表头越过 Overlay；不通过放大 z-index 或恢复模糊修补。空态说明不是禁用控件，使用辅助文字色。

## AppShell 高度与滚动

整个 AppShell 使用 `--radius-shell: 12px`，统一裁切四角，侧栏只跟随左侧外角。既有 Overlay Host 与滚动边界不变。Main 的只读窗口状态由受信任 Preload 写入 `data-window-state`；maximized/fullscreen 时外壳恢复直角。浏览器截图只证明页面裁切，不证明 Windows 窗口外缘圆角。

`NConfigProvider` 必须使用 `abstract`，避免默认 `.n-config-provider` 自动高度中间层破坏百分比高度链。权威布局链为：

```text
html / body / #app = 100%
↓
AppShell = 100% + min-height: 0
↓
Workspace = Topbar + minmax(0, 1fr)
↓
Main Content = 唯一主滚动区
```

禁止通过业务页 `100vh - x` 或固定高度修补 AppShell。

Electron Windows 窗口使用原生 Window Controls Overlay 覆盖现有 54px Topbar。Sidebar Brand 与 Topbar 是统一可拖动区域，Topbar Actions 是明确的 `no-drag` 交互区域；右侧空间通过 `titlebar-area-*` 环境变量避让原生最小化、最大化/恢复和关闭按钮。业务页不得自行添加拖动区域、窗口按钮或标题栏高度。

所有 Drawer、Modal 与动态 Dialog 统一 Teleport 到 AppShell 内的 `AppOverlayHost`。该 Host 从 `--layout-topbar-height` 以下覆盖 Workspace，并建立 Fixed Position Containing Block；业务 Overlay 因而不会进入 Custom Title Bar 或 Window Controls Overlay。业务 Drawer 禁止用单页 `top`、`margin-top` 或固定像素修补。

## Overlay / Dialog 滚动

`AppDialog` 是普通 Dialog/Modal 的唯一视口约束入口。默认最大高度由
`--dialog-max-height` 计算，安全留白统一使用 `--overlay-viewport-safe-gap`；业务组件不得复制
`100dvh - x` 或自定义另一套安全间距。

标准结构固定为：

```text
Header（固定）
↓
Body（flex: 1; min-height: 0；Naive Scrollbar 单一纵向滚动）
↓
Footer（固定）
```

内容较少时 Dialog 保持自然高度且不显示无意义滚动条；内容超过可用视口时只收缩并滚动
Body，标题和操作区始终可见。背景 Page 不参与弹层内容滚动。一个 Overlay 默认只能有一个
主纵向滚动容器；日志、代码等确有独立滚动语义的区域由 Feature 明确设计。Drawer 保持
现有 `AppDrawer` / `NDrawerContent` 布局，不套用 Dialog 内部结构。

## Compact Management Fill 链路

需要将列表 Card 填满筛选区以下剩余工作区时，必须使用可收缩 Flex 链：

```text
Main Content（确定高度）
↓
Page（height: 100%; min-height: 0）
↓
PageSection fill（flex: 1; min-height: 0）
↓
DataTable fill（flex: 1; min-height: 0）
↓
PaginationBar（固定在 Section 底部）
```

数据行保持既有行高；空间不足时仅表格主体使用 Naive DataTable 的必要滚动能力。禁止以固定像素或 `100vh - x` 猜测工作区高度。
