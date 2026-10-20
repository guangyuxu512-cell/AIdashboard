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

### 显式紧凑列表（2026-10-15 候选池试点）

不替换上述默认基线。仅 `density="compact"` 的既有列表边界采用：正文／表头／ID 12px、筛选标签 13px、控件 28px／文字 12px、筛选及列表组合间距 8px、卡片 padding 12px、商品 thumbnail 48px。图片与 8px 上下 padding 自然形成约 64–65px 行，不固定高度裁内容。

尺寸唯一来源为 `tokens.css` 的 `--list-compact-*`；四主题共用尺寸，颜色／字体家族／圆角不变。现有 `--font-size-body`、`--control-height-default`、`--control-height-compact` 等默认值不变。

通过既有 `PageSection`／`FilterBar` 内部 `NConfigProvider abstract` 合并尺寸，保持根 DOM／attrs／fill 链，不能用全局缩放、页面 deep 覆盖或改变默认 Provider。Naive Select 虚拟窗口必须使用可解析像素高度：`createListDensityTheme()` 只为 `InternalSelectMenu.optionHeight` 读取相同 Token 的计算值，其他样式继续使用 CSS 变量。不能以关闭虚拟滚动掩盖尺寸问题。

筛选菜单和 Tooltip 的 Vue provide 随 Teleport 保留；命名 Token 位于全局定义，浮层仍能解析，但默认消费者未引用它们。**Drawer／Dialog 即使 Teleport 到其他 DOM，仍继承其声明位置的主题**，因此候选池详情／编辑 VNode 必须位于紧凑边界外。不要为此修改抽屉／表单内部。

共享默认 `ProductImage` summary 80px、thumbnail 64px；`ProductInfoCell` 默认 ID 13px／复制槽 30px。compact 显式 thumbnail 48px／ID 12px／复制槽 28px，缺图及重试保留同一 48px 槽。详情不得自动缩小：包括未传密度的商品数据详情默认 thumbnail 64px。

候选池、采集任务和商品库业务列表均须显式传 `density="compact"` 才使用紧凑规则；详情 Dialog 保持默认密度。
各 Feature 只配置自身列宽、固定列和交互，不修改共享表格默认样式，也不复制主题颜色。

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
| 布局      | `--layout-*`、`--table-header-height`、`--table-row-height`、`--table-list-viewport-height`   |

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

视觉辨识度调整只能收敛到既有语义 Token 与 Naive UI 全局覆盖：`--border-subtle` 用于可见的层级分隔，`--border-default` 用于可操作控件边界，`--color-primary-soft` 与 `--color-primary` 共同表达选中状态。除下述 primary 按钮映射外，禁用控件继续使用 `--bg-subtle` 和 `--text-disabled`，与正常控件明确区分；业务页面不得自行覆写这些状态色。

禁用 primary 按钮使用共享映射 `--bg-subtle / --border-subtle / --text-tertiary`，不再把边框色当背景；四主题实际文字与图标对比度至少 4.5:1，同时通过中性背景、非主色边框和禁止操作状态与启用态区分。只调整此按钮类型映射，其他控件继续使用原 `--text-disabled`；不新增 token 或页面 CSS，不改变业务禁用条件。

## 全局表面

### 四套主题返修落点

| 预设     | 侧栏      | 页面      | 卡片      | 主按钮    | 辅助色                                               |
| -------- | --------- | --------- | --------- | --------- | ---------------------------------------------------- |
| 石墨浅色 | `#1F2937` | `#F3F4F6` | `#FFFFFF` | `#2563EB` | `#64748B`                                            |
| 森林绿   | `#123E3B` | `#F8FBF5` | `#FFFFFF` | `#2F6F45` | 薄荷 `#DDF7E3`、青柠 `#B7E44B`                       |
| 珊瑚红   | `#F06A6B` | `#FFF9F5` | `#FFFFFF` | `#D52E3B` | 暖橙 `#F4A261`、浅珊瑚 `#FFB4A2`；图表强调 `#E63946` |
| 午夜青   | `#0B1E3F` | `#111827` | `#1F2937` | `#12A08F` | 青绿 `#2DD4BF`、少量暖橙 `#F59E0B`                   |

森林薄荷用于表头/轻层次与选中表面，青柠只用于小面积导航标识；珊瑚侧栏用 `#3B291D` 深色文字/图标（指定初值 `#3D2B1F` 对比度 4.46:1，微调达到 4.59:1）、`#FFB4A2` 选中背景、`#F78982` 悬停背景和 `#E6555B` 分割线，主按钮继续深珊瑚配白字，不把成功/警告语义改红。午夜内容表面采用中性灰明度分层，不延续全蓝工具栏/表头。颜色仍只由 CSS Token 定义，不在页面复制。

Sidebar、Topbar、Surface/Card 与弹层使用纯色和必要的轻阴影，不使用玻璃模糊或大面积渐变。兼容 `--glass-blur` 保留为 0px。普通文字（含辅助、占位、交互文字及按钮各可操作状态）目标对比度至少 4.5:1；禁用态单独检查辨识度，不与可操作状态混淆。中性基础色约 85%、辅助色约 10%、主色约 5% 用于控制视觉份量，不进行像素计数或改变布局凑比例。

移除 `backdrop-filter` 时，以 `isolation: isolate` 保留原 Surface 的层叠边界，避免 DataTable 固定列/表头越过 Overlay；不通过放大 z-index 或恢复模糊修补。空态说明不是禁用控件，使用辅助文字色。

## AppShell 高度与滚动

用户已取消应用外壳圆角需求。AppShell 不设置外壳圆角或投影，也不接收专用窗口状态；桌面外缘使用系统默认窗口行为。卡片、按钮、输入框和弹窗继续使用各自现有圆角 Token。既有 Overlay Host、尺寸和滚动边界不变。

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

Dialog／Drawer 内的 `AppSelect` 菜单也必须脱离可滚动、可裁切的 Overlay Body：应用壳存在时由共享组件挂到 `AppOverlayHost`，登录等无应用壳布局挂到全屏层。不得移除 Host 的视口裁切／Fixed Containing Block，也不得在业务页用 `overflow: visible`、局部 `z-index` 或 `to="body"` 修补单一页面。

## Overlay / Dialog 滚动

`AppDialog` 是普通 Dialog/Modal 的唯一视口约束入口。默认最大高度由
`--dialog-max-height` 计算，安全留白统一使用 `--overlay-viewport-safe-gap`；业务组件不得复制
`100dvh - x` 或自定义另一套安全间距。

数据密集型商品编辑器可显式使用 `AppDialog size="workspace"`：宽度占据
`AppOverlayHost` 可用宽度并保留 8px 外边距，高度占据 Topbar 以下可用高度并保留 8px
外边距。该模式由 `--dialog-width-workspace`／`--dialog-height-workspace` 统一控制，不进入
系统全屏，不改变 `sm/md/lg/xl` 既有消费者，也不得用于普通确认弹窗扩宽。

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
主纵向滚动容器；日志、代码等确有独立滚动语义的区域由 Feature 明确设计。商品编辑
`workspace` 是显式例外：外层 Body 不滚动，左侧编辑区与右侧当前范围列表各自只有一个内部
纵向滚动区，Header 和 Footer 保持固定；不得再嵌套第三个主滚动区。Drawer 保持现有
`AppDrawer` / `NDrawerContent` 布局，不套用 Dialog 内部结构。

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
