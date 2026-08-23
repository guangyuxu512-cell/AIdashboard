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

`DataTable.viewport="stable"` 用于需要稳定分页位置的标准列表管理页：满页、单行、空态、首次加载和错误态共享同一最小视口高度。该能力由表格语义 Token 驱动，页面禁止再写固定高度。

`DataTable.viewport="fill"` 用于列表 Card 必须消费剩余工作区的 Compact Management 页面。它与 `PageSection.fill` 组成 `flex: 1 / min-height: 0` 链，Loading、Empty、Error 和 Table Body 共用剩余主体空间，Pagination 由页面组合固定在底部。空间不足时通过 Naive DataTable `flex-height` 处理表格主体，不拉伸行高。

`DataTable.appearance="list"` 提供无明显纵向网格的列表外观：保留轻量行分隔、表头层级、Hover、Selected 和固定列阴影。默认 `grid` 行为保持不变，必须由页面模式显式选择。

行选择继续使用 Naive UI 原生 selection column，并通过 `checkedRowKeys` / `update:checkedRowKeys` 由 `AppTable`、`DataTable` 统一透传；业务页面不得手写第二套 Checkbox 表头联动。

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

`AppDialog` 同时统一 Viewport 最大高度与内部滚动：Header/Footer 固定，Naive UI
Content Scrollbar 作为唯一 Body 纵向滚动容器。业务 Dialog 只提供内容和可选 Footer
前置操作，不得自行给整张 Modal 或背景 Page 增加滚动补丁。

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

---

## 17. 阶段 0B 基础组件索引

统一从 `@/shared/ui` 导入：

| 组件             | 基础实现       | 项目级默认语义                                   |
| ---------------- | -------------- | ------------------------------------------------ |
| `AppButton`      | `NButton`      | primary / secondary / danger / text，固定 medium |
| `AppInput`       | `NInput`       | 语义宽度、固定 medium                            |
| `AppNumberInput` | `NInputNumber` | 语义宽度、固定 medium                            |
| `AppSelect`      | `NSelect`      | 语义宽度、固定 medium                            |
| `AppDatePicker`  | `NDatePicker`  | date / daterange、语义宽度                       |
| `AppTimePicker`  | `NTimePicker`  | 语义宽度、固定 medium                            |
| `AppSwitch`      | `NSwitch`      | 统一 medium                                      |
| `AppCheckbox`    | `NCheckbox`    | 统一受控布尔值                                   |
| `AppRadio`       | `NRadioGroup`  | 统一 button 模式                                 |
| `AppTable`       | `NDataTable`   | 统一尺寸、边框和滚动入口                         |
| `AppPagination`  | `NPagination`  | 统一 page/pageSize 事件和页容量                  |
| `AppDialog`      | `NModal`       | sm / md / lg、固定 Header/Footer、Body 单滚动    |
| `AppDrawer`      | `NDrawer`      | sm / md / lg、统一内容区                         |
| `AppTabs`        | `NTabs`        | 统一 medium 与动画                               |

宽度只允许 `xs / sm / md / lg / xl / full`，弹层只允许 `sm / md / lg`。低频且没有项目额外语义的 Naive UI 组件继续允许直接使用，不为数量完整性重复封装。

阶段 1B 增加页面模式辅助组件：`FilterField` 统一筛选字段标签和语义宽度，`SummaryGrid` 统一 StatCard 响应式网格。两者只组合既有基础能力，不替代 `AppSelect`、`AppInput` 或 `StatCard`。

阶段 2D-2 起 `FilterField.label` 为可选属性：普通表单式筛选可保留标签，Compact Management Pattern 默认省略标签并依赖控件 Placeholder / Accessible Name 表达含义。`FilterBar` 提供独立 `primary-action` Slot，将新建/添加等主操作与查询、重置放在同一自适应工具栏最右侧。

阶段 2C 增加 `ThemeSelector`，作为 AppShell Topbar 的 Light / Dark / System 入口，内部复用 `AppButton` 和 Naive `NDropdown`。

阶段 2D-1 为既有 `AppDrawer` / `DetailDrawer` 增加通用 `header` Slot，用于领域详情的图标、身份信息和真实操作组合；宽度仍只能使用 `sm / md / lg` 语义尺寸，不新增店铺专用 Drawer。

阶段 2D-4 为 `AppSelect` 增加通用 `renderLabel` 透传，用于 Platform Registry 等领域展示在原有 Select 中组合图标、Label 和支持状态；不得为图标选项创建第二套 Select。

阶段 3A-1 增加 `AppOverlayHost`，由 AppShell 唯一渲染。`AppDrawer`、`AppDialog` 与 `NDialogProvider` 默认挂载到该 Host，使所有业务弹层只覆盖 Topbar 下方 Workspace。基础组件允许为隔离测试显式覆盖 `to`，业务页面不得自行选择 Teleport 容器。

店铺中心与设备中心共用 `ManagementListSection`。它只封装 `PageSection.fill` 与列表内容的 `flex: 1 / min-height: 0` 链，不替代 `DataTable`、`PaginationBar` 或领域工具栏。普通管理列表不得在 Page 内复制这一布局，也不得使用固定高度或 `100vh - xxx` 修正分页位置。

设备身份图标使用统一图标依赖与 `DeviceIdentity` 领域组件，列表和 Drawer 共享同一 Monitor 图标、尺寸和间距；业务页面禁止散落自绘 SVG。

## 18. Design System V2 公共视觉规则

- `ThemeSelector` 是 Topbar 的紧凑主题入口，通过 Naive `NDropdown` 组合既有 `AppButton`，不建立第二套 Button/Dropdown。
- `StatCard` 统一使用相同 Surface，tone 仅改变 2px 轻量 Accent，禁止每张 KPI 使用不同底色。
- `PageHeader`、`PageSection`、`FilterBar` 共享紧凑间距和 Surface Token，不在 Shop/Device 页单独调整。
- 普通列表管理页默认省略 `PageHeader` 和 `PageSection` Header；组件本身继续保留给复杂页面使用。
- `DataTable` 使用实色 Table Surface，统一 Header/Row/Hover/Selected；列表外观不显示明显纵向网格，仅保留极轻横向层次。固定列必须使用语义阴影和不透明单元格，避免滚动时文字叠影。
- `EmptyState`、`LoadingState`、`ErrorState` 共享紧凑状态区高度，禁止列表空态人为占满剩余视口。
- Dialog/Drawer 统一使用 Dark/Light Surface、Border、Overlay Shadow 与紧凑 Padding。
- Naive Provider 统一提供中文 Locale，DatePicker 与 Pagination 不得在中文页面显示默认英文文案。

`Design System Playground` 是开发验收页，必须复用真实基础组件展示 Button、Input、Select、Switch、DatePicker、Status、StatCard、FilterBar、Table、Dialog 和 Drawer。禁止为 Playground 重写仿真组件。
