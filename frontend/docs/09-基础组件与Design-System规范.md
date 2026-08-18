# 09-基础组件与 Design System 规范

## 1. 目的

本规范解决以下问题：

- 不同页面的 Input / Select / Button / DatePicker 大小不一致。
- 同一种状态在不同页面颜色、文字、图标不一致。
- 不同 Agent 为同一类 UI 创建不同实现。
- 页面直接使用 Naive UI 时随意传入 size、style、class，逐渐形成多套视觉规则。
- 公共组件虽然存在，但新页面仍重复实现。

本项目 UI 统一遵循：

```text
Design Token
    ↓
Naive UI Theme Override
    ↓
项目基础 UI 组件
    ↓
页面模式组件
    ↓
领域/业务组件
    ↓
Page
```

任何页面不得绕开这一链路自行建立新的视觉体系。

---

## 2. 组件层级

### 2.1 Design Token

权威来源：

```text
frontend/src/shared/styles/
├── tokens.css
├── typography.css
├── layout.css
└── theme.css
```

Token 负责：

- 字体
- 字号
- 行高
- 间距
- 控件高度
- 圆角
- 边框
- 背景
- 状态颜色
- 阴影
- 页面尺寸

禁止页面直接散落视觉常量。

---

### 2.2 Naive UI Theme Override

Naive UI 的通用视觉配置必须通过全局 Theme Override 对接 Design Token。

优先统一：

- NButton
- NInput
- NInputNumber
- NSelect
- NDatePicker
- NTimePicker
- NCheckbox
- NRadio
- NSwitch
- NDataTable
- NModal
- NDrawer
- NTabs
- NPagination
- NDropdown
- NPopover
- NTooltip

禁止为了调整一个页面而覆盖 Naive UI 内部 DOM 选择器。

---

### 2.3 项目基础 UI 组件

高频、跨页面、需要统一默认行为的组件必须建立项目基础组件。

建议：

```text
shared/ui/
├── AppButton/
├── AppInput/
├── AppNumberInput/
├── AppSelect/
├── AppDatePicker/
├── AppTimePicker/
├── AppSwitch/
├── AppCheckbox/
├── AppRadio/
├── AppTable/
├── AppPagination/
├── AppDialog/
├── AppDrawer/
├── AppTabs/
├── AppTooltip/
└── AppDropdown/
```

这些组件不是重新实现 UI 库。

原则：

```text
AppSelect
    ↓
NSelect
```

项目组件只负责：

- 统一默认尺寸。
- 统一宽度语义。
- 统一状态。
- 统一错误展示。
- 统一项目级默认行为。
- 屏蔽页面随意传入破坏一致性的配置。

---

## 3. 哪些组件必须封装

满足以下任一条件，必须使用项目基础组件，而不是页面直接使用 Naive UI：

1. 跨 2 个以上页面重复使用。
2. 需要统一默认高度、圆角、字号。
3. 需要统一 Loading / Error / Disabled 行为。
4. 需要统一权限行为。
5. 需要统一 Form 错误展示。
6. 页面容易通过 props 改出多套尺寸。
7. 已经存在 App 级组件。

典型必须统一：

- Input
- Select
- Button
- DatePicker
- Pagination
- Table
- Dialog
- Drawer

---

## 4. 哪些 Naive UI 可以直接使用

以下情况允许页面直接使用 Naive UI：

- 低频组件。
- 项目没有额外语义。
- 不存在跨页面视觉一致性风险。
- 不需要增加统一默认行为。

例如可能允许：

- NDescriptions
- NSkeleton
- NTree
- NTimeline

如果后续开始跨多个页面重复使用，则应升级为项目级组件。

---

## 5. 禁止重复组件

开发新页面前必须搜索：

```text
shared/ui
shared/components
entities
features
```

如果已有功能等价组件：

禁止：

```text
TaskSelect.vue
NewTaskSelect.vue
CommonTaskSelect.vue
TaskSelector2.vue
```

必须复用或扩展已有组件。

如果现有组件无法满足：

1. 判断是否属于通用能力。
2. 优先扩展公共组件。
3. 不能为了单页需求破坏公共组件语义。
4. 业务特殊差异应通过 Feature/Entity 组合解决。

---

## 6. 控件尺寸规范

所有基础控件统一使用语义尺寸。

建议基线：

```text
compact: 32px
default: 36px
large:   40px
```

普通后台页面默认使用：

```text
default = 36px
```

禁止页面直接指定：

```text
height: 35px
height: 37px
height: 38px
```

除非新增正式 Design Token。

---

## 7. 控件宽度规范

宽度使用语义尺寸，而不是随机像素。

建议：

```text
field-xs:   120px
field-sm:   160px
field-md:   220px
field-lg:   320px
field-xl:   420px
field-full: 100%
```

例如：

- 状态 Select → sm
- 店铺 Select → md
- 搜索框 → lg
- 普通 Form Input → full / xl

禁止页面自行出现大量：

```text
173px
187px
213px
247px
```

如果确有新的通用尺寸需求，先增加 Token。

---

## 8. Button 规范

按钮至少分为：

- primary
- secondary
- danger
- text/icon

页面不得自行定义新的主按钮颜色。

同一操作语义必须一致：

```text
新建 / 保存 / 确认 → primary
取消 / 返回 → secondary
删除 / 强制停止 → danger
查看详情 → text / secondary
```

一个区域原则上只保留一个视觉主操作。

---

## 9. Table 规范

所有普通业务表格优先使用统一 `AppTable` / `DataTable`。

统一：

- Header 高度。
- Row 高度。
- Empty。
- Loading。
- Error。
- Pagination。
- Selection。
- 操作列。
- 状态列。
- 横向滚动策略。

禁止每个页面分别实现：

```text
loading
empty
pagination
row height
table border
```

---

## 10. Dialog / Drawer 规范

### Dialog
适合：

- 简单编辑。
- 确认操作。
- 中小型 Form。

建议语义宽度：

```text
dialog-sm
dialog-md
dialog-lg
```

### Drawer
适合：

- 详情。
- 较长配置。
- 多区块查看。

建议语义宽度：

```text
drawer-sm
drawer-md
drawer-lg
```

禁止页面随机使用 `537px`、`683px` 等独立尺寸。

---

## 11. Form 规范

统一两种基础布局。

### 普通表单

```text
Label width: 96px
Control height: 36px
Row gap: 16px
```

### 设置类表单

```text
Label width: 120px
Control max-width: 420px
Section gap: 24px
```

所有校验统一：

```text
vee-validate + Zod
```

错误提示位置和样式必须一致。

---

## 12. 状态展示规范

禁止页面自己写：

```ts
if (status === 'RUNNING') color = ...
```

统一建立：

```text
TASK_STATUS_META
DEVICE_STATUS_META
SESSION_STATUS_META
SHOP_STATUS_META
```

每个状态元数据至少包含：

```text
label
tone
icon（需要时）
description（需要时）
```

统一通过 `StatusTag` 展示。

同一个状态在：

- Dashboard
- Task Center
- Detail Drawer
- Device Center

必须完全一致。

---

## 13. 图标规范

优先使用项目已经确定的图标库。

禁止：

- 同一种操作不同页面用完全不同图标。
- 一个页面 SVG，一个页面 Emoji，一个页面另一套 icon 库。
- 为普通功能自行画图标。

新增图标库必须经过明确批准。

---

## 14. 空状态 / 错误 / Loading

统一使用：

- `LoadingState`
- `EmptyState`
- `ErrorState`

禁止页面自行：

```text
<div>暂无数据</div>
```

形成不同视觉。

---

## 15. 强制禁止项

禁止：

- 页面直接设置随机控件高度。
- 页面直接设置随机圆角。
- 页面直接散落业务颜色。
- 同一控件多个近似组件版本。
- 为某一个页面修改全局 Token。
- 通过 `!important` 大面积覆盖组件。
- 大量 deep selector 覆盖 Naive UI。
- 在页面重复实现已有公共能力。
- 为了“效果差不多”自创组件。

---

## 16. 新增基础组件流程

新增前必须回答：

1. Naive UI 是否已有？
2. shared/ui 是否已有？
3. 是否至少会复用 2 次？
4. 是基础 UI，还是业务 Entity/Feature？
5. 是否需要新增 Token？
6. 是否可以通过扩展现有组件解决？

新增后必须：

- 写明确 Props 类型。
- 保持 API 简单。
- 写最小使用示例或测试。
- 更新本规范/组件索引（若属于通用组件）。
