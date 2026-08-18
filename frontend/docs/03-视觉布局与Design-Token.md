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
