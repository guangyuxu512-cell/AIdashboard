# Mobile Visual V2：设备列表

## 状态与参考

状态：**Completed / Candidate for Final Visual Review（已完成 / 候选最终人工视觉复核）**，尚未 Frozen。

本轮只迁移正式 `/devices` 列表页与全局共用 Bottom Navigation 的 V2 视觉。视觉规格来自本机参考文件：
`C:\Users\Administrator\Desktop\device-mobile-iphone13pro-vant4-heartbeat-enabled.html`。该 HTML 只提供
视觉比例、层级、间距和 Light / Dark 方向；生产代码不加载 CDN，不复制 Mock 数据、假状态栏、手机外框、
Home Indicator、Prototype Theme Store、Button 模拟路由或假通知红点。

## Selective Unfreeze（选择性解冻）

本轮明确解冻并迁移：

- `/devices` 页面组合与 Device List 的一级页 Header；
- Hamburger → 正式 Theme / Settings Sheet，以及既有 Theme 快捷切换；
- Search、四项 Summary、DeviceCard、DeviceStatusArtwork 和独立列表滚动；
- `MobileBottomNavigation` 的 V2 视觉，Router 顺序与 Active Contract 不变；
- Mobile 全局系统 Font Family 与 V2 Typography Role；
- 上述稳定 Pattern 的共享组件和 Semantic Token。

未解冻：Backend Contract、DTO、Query Key、Router Contract、Auth/Permission、Device Detail、Task List / Detail、
Schedule、Shop、Me、Capability、Worker 与数据库。旧 Stage 1～3 记录继续作为未迁移组件的 V1 Frozen 历史；
本文件只对显式列出的 Visual V2 条款具有覆盖权。

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

| Pattern           | 正式入口                                                           | 边界                                                               |
| ----------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------ |
| Page Header       | `shared/ui/MobilePageHeader.vue`                                   | Left / centered title / right actions；不替代 `MobileDetailHeader` |
| Search Field      | `shared/ui/MobileSearchField.vue`                                  | 通用输入与 ARIA；不拼 Backend 参数、不内置业务筛选                 |
| Metric Strip      | `shared/ui/MobileSummaryStrip.vue`                                 | 3 / 4 项、selected、disabled、click；不写 Device / Task 分支       |
| List Toolbar      | `shared/ui/MobileListToolbar.vue`                                  | Title / Meta / Selector / Filter；当前 Device 组合不重复渲染       |
| Bottom Navigation | `shared/ui/MobileBottomNavigation.vue`                             | 五等分 Router Navigation、Active 与 Safe Area                      |
| Business Surface  | `.mobile-business-card-surface-v2` + `--visual-v2-business-card-*` | 只共享 Surface / Border / Shadow / Press，不抽万能 Card            |
| DeviceCard        | `features/device-center/ui/DeviceListCard.vue`                     | Device 独有 Anatomy、三态和详情导航                                |
| Device Artwork    | `entities/device/ui/DeviceStatusArtwork.vue`                       | 业务插画，独立于普通 Icon Registry                                 |

这些 Pattern 均为 **Candidate for Freeze（候选冻结）**，等待用户最终人工确认；不得自动迁移其它页面。

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

### Visual V2 Surface / Border Candidate（视觉表面与边界候选）

本表是 `/devices` 当前候选颜色基线，尚未 Frozen。`MobileAppShell` V2 根层是 Page Gradient 的唯一
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

## Device Visual Status（三态设备视觉状态）

公开状态只允许：

1. `connection_status=offline` → `offline` / 离线；
2. `connection_status=online` 且正式 Active Task `status=running` → `running` / 运行中；
3. `connection_status=online` 且无 Running Task → `online` / 在线。

`all` 是 Aggregate Metric / Filter Entry，不是状态。公开 Status Registry、DeviceCard、Artwork State 与 UI
均不存在 `unreported`。Backend 允许 `worker_runtime=null`，但没有第四种公开设备状态；列表使用 Offline
Visual Fallback 以保证确定 UI 状态，不改写 DTO，也不把该 fallback 当作 Backend 返回的离线事实。

Heartbeat 只读取正式 `worker_runtime.last_seen_at` 并复用 Relative Time Formatter；缺失时第三行显示
“心跳未上报”。Heartbeat 的新鲜度不会改变三态，Mobile 不依据时间差发明在线阈值。

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
- 在线、运行中、离线只在所有 Device 分页与 Active Task 事实完整后给出全量数字并启用筛选；
- Search 只在全部分页加载完成后启用，只按正式 `display_name` 本地匹配；
- 不完整时显示 `—` / disabled，不过滤当前页冒充全量，也不发送 `search`、`keyword`、`q` 或 `name`；
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

- Visual Mock：20 台设备，覆盖 Online + Enabled、Online + Disabled、Running + Enabled、Offline + Disabled、
  不同 Heartbeat 与长名称；公开状态只有三种；
- 交互：Theme Sheet、Theme Quick Toggle、四项 Metric、再次点击恢复全部、完整数据 Search、Card → Detail、
  五入口 Router Navigation；
- 数据：部分分页禁用伪全量 Search / Filter，全部事实完成后才启用；
- 视口：360 / 375 / 390 / 430px，Light / Dark；高度 640 / 740 / 844 / 932px；
- 滚动：20 Card 只滚动 List；Header、Search、Summary、Bottom Navigation 不位移；
- 质量：Console Error = 0、Horizontal Overflow = 0、四向 Safe Area 有效、Production 无 Prototype 内容。
