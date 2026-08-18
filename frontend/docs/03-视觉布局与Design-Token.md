# 视觉布局与 Design Token

## 原则
所有页面共享统一视觉基线。
禁止单页自行定义一套字体、间距、圆角、颜色和阴影。

## 建议基线
```text
Sidebar width: 240px
Topbar height: 56px
Page horizontal padding: 24px
Page vertical padding: 20px
Section gap: 16px
Card gap: 16px

Page title: 22px / 600
Section title: 16px / 600
Body: 14px / 400
Secondary: 12px / 400

Control height: 34~36px
Card radius: 8px
Dialog radius: 10px
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

| 类别 | Token |
|---|---|
| 品牌/状态 | `--color-primary*`、`--color-info*`、`--color-success*`、`--color-warning*`、`--color-error*` |
| 文本/表面 | `--color-text-*`、`--color-bg-*`、`--color-border-*` |
| 排版 | `--font-family-base`、`--font-size-*`、`--font-weight-*`、`--line-height-*` |
| 间距 | `--space-1` 至 `--space-8` |
| 控件 | `--control-height-*`、`--field-width-*` |
| 圆角/阴影 | `--radius-*`、`--shadow-*` |
| 弹层 | `--dialog-width-*`、`--drawer-width-*` |
| 布局 | `--layout-*`、`--table-header-height`、`--table-row-height` |

`typography.css` 只负责全局排版基线，`layout.css` 只负责页面和语义宽度布局，`theme.css` 是应用唯一样式入口。Naive UI 的全局覆盖位于 `app/providers/naive-theme.ts`，其尺寸直接引用 CSS Token；需要参与 Naive 颜色计算的值必须在 Provider 创建时从 CSS Token 读取计算值，禁止在 TypeScript 再复制一份颜色常量。
