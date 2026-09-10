# Mobile Visual V2：设备列表

## 状态与参考

状态：**Completed / Frozen（已完成 / 已冻结）**。冻结范围是本文列出的 Visual V2 Shared Foundation
（共享基础）以及 DeviceCard / DeviceStatusArtwork 业务基线，不扩展到 Backend、Query 或其它页面迁移。

本轮只迁移正式 `/devices` 列表页与全局共用 Bottom Navigation 的 V2 视觉。视觉规格来自本机参考文件：
`C:\Users\Administrator\Desktop\device-mobile-iphone13pro-vant4-heartbeat-enabled.html`。该 HTML 只提供
视觉比例、层级、间距和 Light / Dark 方向；生产代码不加载 CDN，不复制 Mock 数据、假状态栏、手机外框、
Home Indicator、Prototype Theme Store、Button 模拟路由或假通知红点。

## Selective Unfreeze Closure（选择性解冻收口）

此前明确解冻并完成迁移：

- `/devices` 页面组合与 Device List 的一级页 Header；
- Hamburger → 正式 Theme / Settings Sheet，以及既有 Theme 快捷切换；
- Search、四项 Summary、DeviceCard、DeviceStatusArtwork 和独立列表滚动；
- `MobileBottomNavigation` 的 V2 视觉，Router 顺序与 Active Contract 不变；
- Mobile 全局系统 Font Family 与 V2 Typography Role；
- 上述稳定 Pattern 的共享组件和 Semantic Token。

本次 Freeze Audit（冻结审计）确认实现与人工确认规范一致，上述范围重新 Frozen。未来确需改变 Anatomy、
Hierarchy、Navigation Contract、Scroll Contract 或视觉基线时必须显式 Unfreeze，禁止在其它阶段顺手修改。

本次列表冻结未解冻 Backend Contract、DTO、Query Key、Router Contract、Auth/Permission、Task List / Detail、
Schedule、Shop、Me、Worker 与数据库。Device Detail 后续已通过独立 Selective Unfreeze 完成 Visual V2
工程化迁移，但仍是 Candidate for Visual Review，其权威条款见
[`11-Mobile-Visual-V2-设备详情.md`](./11-Mobile-Visual-V2-设备详情.md)。本文件只对设备列表及显式列出的共享
Visual V2 条款具有覆盖权。

## 正式页面组合

```text
AppShell（100dvh）
├── MobilePageHeader V2
│   ├── Hamburger → Theme / Settings Sheet
│   ├── Centered Title：设备
│   └── Theme Quick Toggle + Bell（无假红点）
├── Fixed Controls
│   ├── MobileSearchField V2（44px）
│   └── MobileSummaryStrip V2（90px / 4等分）
├── Scrollable Device Card List
└── MobileBottomNavigation V2（64px主体 + Bottom Safe Area）
```

参考 HTML 没有在 Search / Summary 与 Card List 之间重复放置 Toolbar，因此 `/devices` 当前不额外插入
`MobileListToolbar`。该 Shared UI 仍是后续列表页可复用的 V2 Candidate，业务筛选状态不得在 Toolbar 与
Metric Strip 之间维护两份。

## Shared V2 Baseline（共享 V2 基线）

| Pattern                  | 正式入口                                                           | 边界                                                                              | 状态          |
| ------------------------ | ------------------------------------------------------------------ | --------------------------------------------------------------------------------- | ------------- |
| Global Font Family       | `tokens.css` 的 `--font-family-base`                               | 全 Mobile 统一系统字体栈                                                          | **Frozen**    |
| Typography Roles         | `tokens.css` 的 `--typography-v2-*`                                | V2 组件只消费 Semantic Typography Token                                           | **Frozen**    |
| Main Page Shell          | `MobileAppShell.vue` + `.mobile-list-page*`                        | 真实 Viewport、四向 Safe Area、固定顶部/底部与中间独立滚动                        | **Frozen**    |
| Page Header              | `shared/ui/MobilePageHeader.vue`                                   | Left / centered title / right actions；不写死 Device，不替代 `MobileDetailHeader` | **Frozen**    |
| Search Field             | `shared/ui/MobileSearchField.vue`                                  | 44px、通用输入与 ARIA；不拼 Backend 参数、不内置业务筛选                          | **Frozen**    |
| Metric Strip             | `shared/ui/MobileSummaryStrip.vue`                                 | 3 / 4 项、Number / Label、selected、disabled、click；不写业务分支                 | **Frozen**    |
| Bottom Navigation        | `shared/ui/MobileBottomNavigation.vue`                             | 设备 / 任务 / 计划 / 店铺 / 我的五等分、Router Active 与 Safe Area                | **Frozen**    |
| Business Card Surface    | `.mobile-business-card-surface-v2` + `--visual-v2-business-card-*` | 共享 Surface / Border / Radius / Shadow / Touch / Trailing / Gap，不抽万能 Card   | **Frozen**    |
| DeviceCard               | `features/device-center/ui/DeviceListCard.vue`                     | Device 独有 Anatomy、连接/运行事实与详情导航                                      | **Frozen**    |
| DeviceStatusArtwork      | `entities/device/ui/DeviceStatusArtwork.vue`                       | 设备业务插画，只公开 Online / Running / Offline，独立于普通 Icon Registry         | **Frozen**    |
| Page Background Language | `tokens.css` + `MobileAppShell.vue`                                | Shell 唯一绘制连续背景，Safe Area / Header 透明，Search / Summary / Card 独立绘制 | **Frozen**    |
| MobileListToolbar V2     | `shared/ui/MobileListToolbar.vue`                                  | `/devices` 未实际使用，等待真实列表场景验证                                       | **Candidate** |

Task、Shop、Schedule 后续迁移必须优先复用 Global Typography、Main Page Shell、Page Header、Search Field、
Metric Strip、Bottom Navigation 与 Business Card Surface。页面可以自行提供业务 Metric、业务 Card、筛选逻辑、
搜索 Contract 与 Query；DeviceCard / DeviceStatusArtwork 不得复制成其它实体结构。禁止创建 UniversalDashboard、
万能 Page Schema、万能 BusinessCard 或低代码 UI Engine。

## Global Typography V2（全局字体排版）

正式系统字体栈：

```text
-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display",
"PingFang SC", "Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei", sans-serif
```

不下载或打包 Apple 字体。V2 Semantic Role 全部来自 `tokens.css`：

| Role                    | Size / Weight / Line Height     |
| ----------------------- | ------------------------------- |
| Page Title              | 20 / 600 / 24px                 |
| Detail Title            | 20 / 600 / 24px（后续 V2 预留） |
| Business Card Title     | 16.5 / 600 / 19.8px             |
| Search                  | 16 / 500 / 20px                 |
| Status                  | 14 / 500 / 14px                 |
| Meta                    | 13 / 400 / 13px                 |
| Tag                     | 12 / 500 / 15px                 |
| Metric Number           | 23 / 600 / 23px                 |
| Metric Label            | 12.5 / 450 / 14.75px            |
| Bottom Navigation Label | 12 / 500 / 15px                 |

未迁移页面只继承统一 Font Family，不在本轮被强制重排字号和结构。

## 几何与 Surface 基线

| 区域                        | 基线                                                                    |
| --------------------------- | ----------------------------------------------------------------------- |
| Page Header                 | 66px；18px 水平留白；40px 可见 Action Surface；触控区 >=44px            |
| Search                      | 44px；圆角 22px                                                         |
| Summary                     | 90px；圆角 18px；四等分                                                 |
| Metric Number / Label       | 23px / 600；12.5px / 450                                                |
| Device Card                 | 最小 122px；圆角 17px；列表间距 14px                                    |
| Card Grid                   | 102px Artwork / `minmax(0, 1fr)` Content / 18px Chevron                 |
| Card Padding                | Top 15 / Right 17 / Bottom 15 / Left 16px                               |
| Device Name / Status / Meta | 16.5px / 600；14px / 500；13px / 400                                    |
| Artwork Container           | 80×80px；Kind 与 State 分离                                             |
| Bottom Navigation           | 64px 主体；18px 水平留白；8px 上下留白；25px Icon；4px Icon / Label Gap |

几何只来自 `--typography-v2-*`、`--visual-v2-*`、`--device-list-*` 与 `--device-artwork-*`。Light / Dark
Surface、Border、Shadow 也只通过 Semantic Token 解析；Vue 组件不得散落 Hex、Radius、Shadow 或同义尺寸。

### Visual V2 Surface / Border Frozen Baseline（视觉表面与边界冻结基线）

本表是 `/devices` 当前 Frozen 颜色基线。`MobileAppShell` V2 根层是 Page Gradient 的唯一
绘制者；顶部 Safe Area 容器、`MobilePageHeader` 与 Device Page 内容层必须保持透明并显示同一连续背景，
禁止各自复制渐变或绘制独立 Header Surface。Search、Summary 与 DeviceCard 继续拥有各自的语义 Surface，
禁止回退到旧 Stage 3A 的 `--bg-*` Surface。

| Layer（层）                   | Background Ownership（背景归属）                                   |
| ----------------------------- | ------------------------------------------------------------------ |
| Visual V2 AppShell Root       | `--visual-v2-page-background`，唯一绘制完整 Light / Dark Page 背景 |
| Top Safe Area / Page Header   | `--visual-v2-page-header-background: transparent`，透出 Shell 背景 |
| Device Page / Controls 外部区 | 透明，不重复绘制 Page Gradient                                     |
| Search / Summary / DeviceCard | 分别消费自己的 Visual V2 Semantic Surface                          |

| Theme | Page Gradient / Safe Area     | Search / Weak Surface | Summary / Card | Card Border | Divider   |
| ----- | ----------------------------- | --------------------- | -------------- | ----------- | --------- |
| Light | `#FBFCFE → #F4F7FB → #F2F5FA` | `#F1F4F8`             | `#FFFFFF`      | `#E7EBF1`   | `#E8EDF4` |
| Dark  | `#07111D → #081521`           | `#182638`             | `#101D2D`      | `#27374A`   | `#27374A` |

Bottom Navigation 保留参考 HTML 的半透明 Surface：Light 为 `rgb(255 255 255 / 95%)`，Dark 为
`rgb(8 18 30 / 92%)`；其 Safe Area 使用对应不透明底色 `#FFFFFF` / `#081521`，避免真机刘海与 Home
Indicator 区域露出旧主题 Surface。

## Device Visual Status（设备视觉状态）

公开 Artwork 状态固定为：

1. `connection_status=offline` → `offline` / 离线；
2. `connection_status=online` 且正式 Active Task `status=running` → `running` / 运行中；
3. `connection_status=online` 且无 Running Task → `online` / 在线。

`all` 是 Aggregate Metric / Filter Entry，不是状态。公开 Artwork Registry 不增加 `unreported`；
`worker_runtime=null` 时，Frozen Artwork 继续使用 `offline` visual fallback，但独立 Connection Display Meta 使用
`unreported` 并在正式 UI 显示“未连接”。该文字展示态不是 Backend `connection_status` 或 Artwork State，
不得改写 DTO，也不得计入离线统计或筛选。本次筛选修复不改变 DeviceCard / Artwork 的 Frozen Anatomy、
Geometry、Color、Navigation 与 Scroll Contract。

Heartbeat 只读取正式 `worker_runtime.last_seen_at` 并复用 Relative Time Formatter；缺失时第三行显示
“心跳未上报”。Heartbeat 的新鲜度不会改变展示状态，Mobile 不依据时间差发明在线阈值。

`enabled` 只读取正式 `Device.enabled`，显示“已启用 / 已停用”；它不改变连接、Active Task、Artwork 或状态。
DeviceCard 第三行固定为 `Heartbeat Icon + 心跳相对时间 + · + 启用状态`，不再展示 Worker Version。

## DeviceStatusArtwork 与 Device Kind

`DeviceStatusArtwork` 是 Business Illustration，不是 Utility Icon，因此不进入 `MobileIcon` Registry。普通
Icon Registry 继续负责 Search、Menu、Theme、Bell、Heartbeat、Chevron、Bottom Navigation、Back 与 Refresh。

Artwork 接收 `kind` 与 `state` 两个独立输入。当前 Backend 没有正式 Device Kind 字段，Production 统一使用
`desktop` fallback；禁止按设备名、位置、Worker Version 或 Provider 猜 desktop / laptop / server。组件测试
可验证三种 Kind 的视觉容量，正式映射必须等待 Backend Contract。

## Summary、Filter 与 Search

Summary 顺序固定为：全部设备、在线设备、运行中、离线设备。四项消费同一个 `DeviceQuickFilter`；点击切换，
再次点击当前非全部项恢复全部，触控区至少 44×44px。

Backend Device List 只支持 `page`、`page_size`，没有服务端 Search、Connection Status 或 Active Task 筛选：

- “全部设备”读取 Backend `total`；
- 在线、运行中、离线只在所有 Device 分页及对应 Active Task 事实完整后给出全量数字；
- 首屏 Device List 成功后四项 Metric 与 Search 即可操作；筛选/搜索意图出现时，Mobile 通过正式
  `page/page_size` 可控补齐剩余分页，补齐期间保持唯一 Filter State 的选中反馈并显示“正在筛选”；
- 补齐失败显示“筛选失败 / 重试”，不渲染局部分页过滤结果；再次点击当前 Metric 恢复全部，0 条结果仍可选中并显示“没有设备”；
- Search 只按正式 `display_name` 本地匹配，并与同一个 `DeviceQuickFilter` 组合；不发送 `search`、`keyword`、`q` 或 `name`；
- 服务端 Search、聚合统计、批量 Active Task 与 Device Kind 均记录为 Contract Gap，本轮不改 Backend。

## Theme、Settings 与 Navigation

Hamburger 打开 `MobileThemeSettingsSheet`，只操作现有 Theme Store 的 Light / Dark / System；右侧 Theme Action
继续快速切换已解析主题。Bell 没有正式通知数据时不显示 Dot。不得创建第二套 Theme State。

Bottom Navigation 固定顺序：设备、任务、计划、店铺、我的，Active 继续由 Vue Router 决定。V2 只改变视觉，
不复制 Prototype Button Navigation。主体 64px 使用 `border-box`，Bottom Safe Area 仍由 AppShell Footer 独立
拥有；不绘制 Fake Home Indicator。

## Responsive 与 Scroll Contract

`390 × 844` 仅为 iPhone 13 Pro 视觉验收基准。生产：

- `width: 100%`，AppShell 使用 `100dvh`；
- 不写死 390px / 844px，不使用整页 `transform: scale()`；
- Header、Search、Metric Strip 与 Bottom Navigation 保持自身尺寸；
- Device List 使用 Flex/Grid 剩余空间、`min-height: 0` 与 `overflow-y: auto`；
- 只有 Device List 滚动，Document、Header、Fixed Controls 与 Bottom Navigation 不滚动；
- Top / Right / Bottom / Left Safe Area 均由既有语义消费；
- 360 / 375 / 390 / 430px 与 640 / 740 / 844 / 932px 高度自然适配。

## 验收

- Real Page Fixture：超过一页设备，覆盖 Online Idle、Online Running、正式 Offline、Runtime Unreported、
  不同 Heartbeat、长名称与 0 条筛选结果；
- 交互：Theme Sheet、Theme Quick Toggle、四项 Metric、再次点击恢复全部、完整数据 Search、Card → Detail、
  五入口 Router Navigation；
- 数据：部分分页点击后可控补齐、准备/失败反馈、全量后过滤、搜索组合、下拉刷新与 Active Task 后台更新；
- 视口：360 / 375 / 390 / 430px，Light / Dark；高度 640 / 740 / 844 / 932px；
- 滚动：20 Card 只滚动 List；Header、Search、Summary、Bottom Navigation 不位移；
- 质量：Console Error = 0、Horizontal Overflow = 0、四向 Safe Area 有效、Production 无 Prototype 内容。
