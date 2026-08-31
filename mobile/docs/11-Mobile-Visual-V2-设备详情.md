# Mobile Visual V2：设备详情

## 状态与参考

状态：**Completed / Frozen（已完成 / 已冻结）**。本文只覆盖 `/devices/:deviceId` 的 Visual V2 页面组合、
详情专属组件，以及由本页完成真实场景验证的共享模式。

详情视觉参考为本机文件 `C:\Users\Administrator\Desktop\设备卡详情.html`。参考 HTML 只决定详情页的
Composition（页面组合）、比例、层级和 Light 方向；生产实现不复制假 9:41、信号/Wi-Fi/电池、Home
Indicator、固定 428×926 Phone Shell、CDN、Mock Device/Task/Application、Prototype Theme Store 或
`setTimeout` 假成功。

优先级固定为：已冻结的 Mobile Visual V2 Shared Foundation → 本文详情 Composition → 正式 Backend / Query
Contract → 旧 Mobile V1 Device Detail。业务事实永远不被视觉稿覆盖。

## Selective Unfreeze Closure（选择性解冻收口）

以下范围曾显式解冻并迁移，现已完成人工确认并重新冻结：

- Device Detail Page Composition；
- 旧 `DeviceRuntimeSummary` V1 在 `/devices/:deviceId` 的页面职责；
- Device Detail Capability Panel 的视觉组合；
- Current Task 的详情上下文视觉；
- 旧 More Information 区的呈现方式。

未解冻：`/devices` 列表、`DeviceCard V2`、`MobileAppShell V2`、Page Background V2、Global Typography
Foundation、`MobileBottomNavigation V2`、Router、Query Key、Backend Contract、Auth/Permission、Task List /
Task Detail、Worker 与数据库。

本次冻结包括：`/devices/:deviceId` Composition、`MobileDetailHeader V2`、`DeviceDetailHero V2`、
`MobileBusinessCardFrame V2`、`TaskCard V2` 共享三行骨架、`DeviceCapabilityPanel V2` 视觉结构、
`DeviceStatusArtwork` hero variant、Current Task → TaskCard V2 复用关系、详情主滚动区、Bottom Navigation V2
复用关系，以及 Light / Dark Visual V2 映射。后续若需改变 Anatomy、Hierarchy、Geometry、Navigation、Scroll
或 Theme Mapping，必须先明确提出 Unfreeze 并重新完成人工验收。

## Prototype → Production Mapping

| HTML 结构            | Production 实现                                                | 边界                                                              |
| -------------------- | -------------------------------------------------------------- | ----------------------------------------------------------------- |
| `detail-header`      | `shared/ui/MobileDetailHeader.vue` V2                          | Left Action + 真居中 Title + Right Action；透明承接 AppShell 背景 |
| `device-hero`        | `features/device-center/ui/DeviceDetailHero.vue`               | 详情专属业务 Hero，不放大 DeviceCard                              |
| `monitor`            | `entities/device/ui/DeviceStatusArtwork.vue` 的 `hero` variant | 复用公开三态插画，不复制第二套 Monitor                            |
| `entity-card`        | 正式 `entities/task/ui/TaskListCard.vue` 的显式 V2 模式        | 真实 Active Task；无局部 Task Card 副本                           |
| `capability`         | 正式 `features/device-center/ui/DeviceCapabilityPanel.vue` V2  | 复用 Provider / Skill Query 与业务映射                            |
| `bottom-nav`         | 已冻结 `MobileBottomNavigation V2`                             | Router 决定设备入口 Active                                        |
| `phone-bottom-sheet` | Vant 4 `Popup` + `DeviceMoreSheet.vue`                         | 只读真实信息；不复制 Popup 基础设施                               |

## 正式页面组合与滚动

```text
MobileAppShell V2（100dvh）
├── MobileDetailHeader V2（固定）
├── AppPage（唯一主滚动区域）
│   ├── DeviceDetailHero V2
│   ├── Current Task
│   ├── DeviceCapabilityPanel V2
│   └── DeviceMoreSheet（按需 Vant Overlay）
└── MobileBottomNavigation V2（固定）
```

`AppPage` 使用 Flex 剩余空间、`min-height: 0` 和 `overflow-y: auto`；Capability 只有 Row List 内部滚动，
Header 与 Tabs 不滚动。Document 不承担业务滚动。Top Safe Area、透明 Detail Header 与页面底层继续由同一个
AppShell Page Background 绘制；Bottom Navigation 独立拥有 Bottom Safe Area。

428×926 只作为 HTML 设计对照。生产必须使用 `width: 100%`、真实 `100dvh` 和四向
`env(safe-area-inset-*)`，不得固定 428/926、不得固定 390/844，也不得整页 `transform: scale()`。至少验证
360 / 375 / 390 / 428 / 430px 宽度和 640 / 740 / 844 / 926 / 932px 高度。

## Reused Frozen V2 Foundation（复用冻结基础）

- `MobileAppShell V2`、连续 Page Background、四向 Safe Area 与页面滚动所有权；
- Global Font Family V2 与既有 Typography V2 基础角色；
- `MobileBottomNavigation V2`、五入口顺序、Router Active 与触控契约；
- Business Card Surface V2 的 Surface / Border / Radius / Shadow / Press 语言；
- `DeviceStatusArtwork V2` 的 Online / Running / Offline 三态语义；
- Mobile Icon Registry 的 Back、More、Refresh、Chevron、Task 与 Capability Glyph；
- Light / Dark / System Theme Store 与 Semantic Color Token。

## Frozen Shared V2 Patterns（已冻结共享模式）

| Pattern               | 文件                                    | 职责与复用边界                                                                              | 状态       |
| --------------------- | --------------------------------------- | ------------------------------------------------------------------------------------------- | ---------- |
| MobileDetailHeader V2 | `shared/ui/MobileDetailHeader.vue`      | Left / Center Title / Right Action、透明背景；业务页只注册 Action                           | **Frozen** |
| BusinessCardFrame V2  | `shared/ui/MobileBusinessCardFrame.vue` | Surface、102px Leading Column、三行 Main Content、18px Trailing、触控与对齐；不包含业务状态 | **Frozen** |
| TaskCard V2           | `entities/task/ui/TaskListCard.vue`     | 复用正式 Task 状态与 Meta；由调用方显式开启 V2，本轮不迁移 `/tasks`                         | **Frozen** |

`BusinessCardFrame V2` 不是万能业务 Card。Device、Task 与未来 Shop 继续在自己的 Entity / Feature 中处理
Artwork、状态和业务字段；Shared 不出现 `deviceMode/taskMode/shopMode` 分支。为抽取 Frame 而做的
`DeviceCard V2` 内部重构必须保持其冻结 DOM 语义和 Computed Geometry 0 变化。

## DeviceDetailHero V2

Hero 固定为 Device Artwork + Device Name + Visual Status + Heartbeat + 可选 Detail Meta。它是
Device Feature 组件，不使用 `BusinessCardFrame V2`。

- Device Name：`22px / 600 / 26px`，单行 Ellipsis；
- Visual Status：`16px / 500 / 16px`；
- Heartbeat / Hero Meta：`14px / 400 / 18px`；
- Artwork：复用 `DeviceStatusArtwork variant="hero"`；List variant 的视觉必须 0 变化；
- 状态：复用列表同一个 `getDeviceVisualState`，只公开 Online / Running / Offline；
- Heartbeat：只格式化正式 `worker_runtime.last_seen_at`，不参与在线阈值；
- Meta：只显示存在的 Worker Version 和影刀 Provider Version；一个事实时自然单列，不为对称造第二个。

当前 Backend 没有 Device Kind 与用户编号 Contract，因此 Production 继续使用 `desktop` fallback；不显示
Prototype 的 `GY00099`，不把 UUID 当用户编号，也不根据设备名、IP 或版本猜 Kind。

Hero 冻结几何：214px Min Height，`24 / 22 / 20 / 22px` 四向 Padding，138px Leading Column，122px
Artwork Height；详情 Section Gap 为16px。所有值只存在于 `tokens.css` 的 Visual V2 Detail Semantic Token。

## Business Card Unification（业务卡片统一）

DeviceCard V2 与 TaskCard V2 共享：122px Min Height、`102px minmax(0, 1fr) 18px` Grid、
`15px 17px 15px 16px` Padding、`16.5 / 14 / 13px` 的 Title / Status / Meta 角色、Chevron 位置与 Business
Card Surface。正文起始 X、三行 Baseline 语言和 Trailing 对齐必须一致。

不同点仅是业务内容与 Leading Visual：DeviceCard 使用80×80 `DeviceStatusArtwork`；TaskCard 在同一个102px
Leading Column 内居中54px Task Tile 和28px Task Glyph。不得把 Task Icon 撑满 Leading Column。

`/tasks` 本轮继续使用原有 Task List 视觉；只有 Device Detail Current Task 显式开启 V2。后续 Task List V2
必须复用同一个 `TaskListCard` V2 模式，不得再创建 `TaskListCardV2` 或 `DeviceCurrentTaskCard`。

## Current Task

Current Task 复用正式 `GET tasks/active/{device_id}` Query、`ActiveTaskSummaryReadDto`、Task Status Metadata 与
`mapDeviceActiveTaskToTaskListItem` 最小适配：

- Active Task 存在：渲染正式 `TaskListCard` V2，整卡进入 `/tasks/:taskId`；
- 导航保留 `fromDeviceId`，Task Detail 返回原设备详情；
- `204` / 正式 `null`：只显示“空闲”；
- 初次 Loading / Error 独立于 Device 主数据，辅助 Query 不阻塞已成功的详情；
- Background Error 保留已有成功数据；
- Prototype 的“订单18/46”没有正式 Contract，不进入 Production。

## Capability Panel V2

正式数据仍来自 `GET devices/{id}/provider-inventories` 与
`GET devices/{id}/skill-capabilities`：

- Tabs 固定为“影刀应用 N / Skills N”；Apps 读取影刀 Inventory Applications，Skills 只读取
  `classification=business`；
- Row 为 Icon Slot + Name / Optional Version + Configure / Run；Application 技术 `version_id` 不当可读版本，
  Business Skill 可显示正式 `version`；
- Skill 仅在 `input_schema !== null` 时显示“配置”；长名称 Ellipsis 且 Actions 保持可见；
- Refresh 真实并行 refetch Provider Inventory 与 Skill Capability Query，不使用 Prototype `setTimeout`；
- Configure / Run 当前没有正式 Mobile Mutation，只显示“功能建设中”，不发送写请求、不显示 Fake Success；
- Application / Skill UUID 不进入正常 Row；技术 ID 和非核心 Provider / Skill 信息只进入“更多信息”；
- Header 与 Tabs 固定，Row Height 66px，List Height `66px × 5`；完整显示五行，第六行开始内部滚动且不露半行。

Capability 图标继续经过 Mobile Icon Registry 的类型映射；不复制 HTML 的内联 SVG Registry，不在组件散落
steel/sage/clay/mauve/slate Hex Palette。

## More Sheet

Header 的 More Action 打开 Vant 4 Bottom Popup。Sheet 只读展示正式 Device、Worker Runtime、Provider 与
Skill Capability 信息，包括 Device ID、启用状态、位置、备注、更新时间、Worker 版本/时间和已有详情组件。
它不提供停用、删除、绑定、启动、停止、配置或设置等写操作。

Prototype 的“设备配置”“更多设置”和假 Action 不迁移；Sheet 使用 Visual V2 Surface、Vant Cell、四向 Safe
Area 和已有 Theme Store，不创建 Device 私有 Popup、Theme 或 API。

## Light / Dark

详情页不定义局部色值。Light / Dark 均消费已冻结的 Visual V2 Semantic Token：Page Background 由 AppShell
唯一绘制；Header 透明；Hero、Current Task、Capability 与 Sheet 使用正式 Card / Weak / Border / Divider /
Status 语义。Dark 继续使用已冻结的 `#07111D → #081521` Page 语言、`#101D2D` Card、`#182638` Weak 与
`#27374A` Border；这些值只记录基线，组件不得写 Hex。

## Contract Gaps 与 Prototype 差异

| Prototype 内容        | Production 处理                                                             |
| --------------------- | --------------------------------------------------------------------------- |
| `GY00099`             | 删除；Backend 无普通用户 Device Code                                        |
| 固定“影刀 v5.36.1”    | 仅在正式 Provider Inventory 提供版本时显示真实值                            |
| 固定“订单18/46”       | 删除；Active Task Summary 无该进度事实                                      |
| 固定 Desktop 类型     | 保留为明确 Contract Gap 下的 `desktop` visual fallback，不声称 Backend Kind |
| Mock Apps / Skills    | 替换为 Provider Inventory / Business Skill 正式 Query                       |
| `setTimeout` 刷新成功 | 替换为真实 Query refetch；不显示假成功                                      |
| 假配置/运行结果       | 不发 Mutation，只保留候选入口并显示“功能建设中”                             |
| 假设备设置 Action     | 不迁移；More Sheet 只读                                                     |

Backend、Worker 与数据库在本轮保持 0 修改。

## 验收

- 路由：DeviceCard → `/devices/:deviceId`、Back → `/devices`、Current Task → `/tasks/:taskId`、返回设备详情、
  Bottom Navigation 设备入口 Active；
- 状态：Device Initial Loading / Error、Active Task Loading / Error / Idle、Provider / Capability Loading /
  Error 与背景刷新互相独立；
- 数据：三态复用、真实 Heartbeat、真实 Worker / Provider Version、Business Skill 分类、无 Prototype 字段；
- Capability：Tabs、真实 Refresh GET、无写请求、五行完整、第六行内部滚动、外层详情继续可滚；
- 响应式：360 / 375 / 390 / 428 / 430px，640 / 740 / 844 / 926 / 932px，Light / Dark；
- 长文本：Device / Task / Capability Name 单行 Ellipsis，Actions 与 Chevron 保持可见；
- 回归：`/devices`、DeviceCard V2、AppShell V2、Bottom Navigation V2、Page Background V2 与 `/tasks`
  原有列表视觉均不回归；
- 质量：Console Error = 0、Horizontal Overflow = 0、组件无颜色字面量、Production 无 Mock。

`MobileDetailHeader V2`、`BusinessCardFrame V2`、`TaskCard V2`、`DeviceDetailHero V2` 与
`CapabilityPanel V2` 已随 Device Detail Visual V2 完成人工确认并冻结。冻结不新增 Backend 写操作、不改变
Query / Router，也不自动迁移 `/tasks`；Task List Visual V2 必须在独立分支和独立任务中开始。
