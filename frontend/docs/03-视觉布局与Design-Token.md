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

Page title: 20px / 600
Section title: 15px / 600
Body: 14px / 400
Secondary: 12px / 400

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

## 阶段 0B 已建立 Token

权威文件：`frontend/src/shared/styles/tokens.css`。

| 类别      | Token                                                                                         |
| --------- | --------------------------------------------------------------------------------------------- |
| 品牌/状态 | `--color-primary*`、`--color-info*`、`--color-success*`、`--color-warning*`、`--color-error*` |
| 文本/表面 | `--color-text-*`、`--color-bg-*`、`--color-border-*`                                          |
| 排版      | `--font-family-base`、`--font-size-*`、`--font-weight-*`、`--line-height-*`                   |
| 间距      | `--space-1` 至 `--space-8`                                                                    |
| 控件      | `--control-height-*`、`--field-width-*`                                                       |
| 圆角/阴影 | `--radius-*`、`--shadow-*`                                                                    |
| 弹层      | `--dialog-width-*`、`--drawer-width-*`                                                        |
| 布局      | `--layout-*`、`--table-header-height`、`--table-row-height`、`--table-list-viewport-height`    |

`typography.css` 只负责全局排版基线，`layout.css` 只负责页面和语义宽度布局，`theme.css` 是应用唯一样式入口。Naive UI 的全局覆盖位于 `app/providers/naive-theme.ts`，其尺寸直接引用 CSS Token；需要参与 Naive 颜色计算的值必须在 Provider 创建时从 CSS Token 读取计算值，禁止在 TypeScript 再复制一份颜色常量。

`--table-list-viewport-height` 是标准 10 行管理列表的稳定视口高度，由表头、包含标准操作控件的行槽、每页数量和分隔线 Token 推导。`--table-row-height` 仍表达普通文本行密度，`--table-list-row-slot-height` 表达列表操作行的实际占位。业务页面不得复制计算式或另写像素高度；空态、单行和满页状态均复用该语义 Token，Pagination 因而保持在稳定位置。

## 阶段 2C 主题与语义 Token

Theme Store 正式支持 `light`、`dark`、`system`。模式保存于 Renderer `localStorage`，`system` 通过 `prefers-color-scheme` 实时跟随系统。Electron 桌面环境只通过类型化 `window.desktop.appearance.setTitleBarTheme` 接收解析后的 Light / Dark 结果，用于同步原生 Window Controls Overlay 图标颜色；Web 环境保持无 Electron 依赖。

Token 分层：

```text
Base Token
├── Typography / Spacing / Density / Radius / Layout
└── Light / Dark Semantic Token
    ├── Accent
    ├── Text
    ├── Surface
    ├── Border / Shadow
    └── Status
```

新的全局实现应优先使用 `--text-*`、`--bg-*`、`--border-*`、`--status-*` 语义 Token。`--color-text-*`、`--color-bg-*` 等旧名称仅作兼容别名，不得在业务页新增随机颜色。

## 企业级 Frosted Glass

毛玻璃只用于 Sidebar、Topbar 和主 Surface/Card，默认 Blur 为 10px，配合低透明度表面、1px 边框与轻阴影。Table Cell、Button、Input、Select 不使用 Blur。页面背景使用中性冷灰，禁止蓝紫青渐变、Neon、Glow 和大面积高饱和颜色。

## AppShell 高度与滚动

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
