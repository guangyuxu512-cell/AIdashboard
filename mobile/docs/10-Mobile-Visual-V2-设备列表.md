# Mobile Visual V2：设备列表

## 状态与参考

状态：**Completed / Candidate for Visual Review（已完成 / 候选人工视觉复核）**。

本轮只迁移正式 `/devices` 列表页。视觉规格来自本机参考文件：
`C:\Users\Administrator\Desktop\device-mobile-iphone13pro-vant4-heartbeat-enabled.html`。
该 HTML 只提供视觉比例、层级、间距、状态呈现和 Light / Dark 方向，不是运行时依赖，也不是可复制的
独立应用。生产代码不加载 CDN，不复制 Mock 数据、假状态栏、设备外框、Home Indicator、汉堡菜单、
主题调试面板或通知红点。

## Selective Unfreeze（选择性解冻）

本轮明确解冻并迁移：

- `/devices` 页面组合与一级页 Header 呈现；
- Search、四项 Summary 和设备 Card List；
- DeviceCard 的 V2 Anatomy、设备状态插画和列表滚动边界；
- 仅服务于上述结构的集中 Visual V2 Semantic Token。

未解冻：Backend Contract、DTO、Query Key、Router、Auth/Permission、Bottom Navigation、Task 页面、
Device Detail、Task Detail、Capability、Worker 与数据库。旧 Stage 1～3 的记录继续作为未迁移组件的正式
历史基线；本文件只对 `/devices` 的冲突条款具有覆盖权。任何后续结构变化仍需显式 Unfreeze。

## 响应式与滚动契约

`390 × 844` 仅是 iPhone 13 Pro 的设计与截图对照基准，不是生产尺寸。正式页面：

- 宽度跟随实际 viewport，使用 `width: 100%`；
- 高度由既有 `100dvh` AppShell 与 Flex/Grid 剩余空间分配，不固定 `844px`；
- 不使用 `transform: scale()` 对整页等比缩放；
- Header、Search/Summary 固定区和 Bottom Navigation 保持各自设计尺寸；
- Device Card List 使用 `minmax(0, 1fr)` 获得剩余高度并独立纵向滚动；
- Shell、固定区和列表分别消费既有 `safe-area-inset-top/right/bottom/left` 语义；
- 360、375、390、430px 宽度以及 640、740、844、932px 等不同高度必须自然适配。

文档和 Playwright 可以使用 390×844 生成主要验收截图；生产 Vue/CSS 禁止出现固定 390px 宽、844px 高
或只对某一机型成立的整体缩放。

## 页面结构与正式视觉基线

```text
AppShell
├── Device Page Header（设备 + Theme + Bell）
├── Fixed Controls
│   ├── Search（44px）
│   └── Summary（90px / 4等分）
├── Scrollable Device Card List
└── Existing Bottom Navigation
```

正式几何基线：

| 区域                  | 基线                                                    |
| --------------------- | ------------------------------------------------------- |
| Page Header           | 66px；标题约 20px / 600                                 |
| Search                | 44px；圆角 22px                                         |
| Summary               | 90px；圆角 18px；四等分                                 |
| Metric Number / Label | 23px / 600；12.5px / 450                                |
| Summary → First Card  | 14px 列表起始留白                                       |
| Device Card           | 最小 122px；圆角 17px；列表间距 14px                    |
| Card Grid             | 102px Artwork / `minmax(0, 1fr)` Content / 18px Chevron |
| Card Padding          | Top 15 / Right 17 / Bottom 15 / Left 16px               |
| Device Name           | 16.5px / 600；单行省略                                  |
| Status / Meta         | 14px / 500；13px / 400                                  |
| Artwork Container     | 80×80px；Kind 与状态分离                                |

这些值只通过 `mobile/src/shared/styles/tokens.css` 的 `--device-list-*` 与 `--device-artwork-*` 集中语义
Token 提供。它们是这次明确迁移的页面 Pattern Token，不允许在 Vue 组件散落 Hex、Shadow、Radius 或尺寸
字面量；也不得反向修改 PC Token。

## Summary、搜索与完整数据边界

Summary 固定为：全部设备、在线设备、运行中、离线设备。四项都使用同一个 `DeviceQuickFilter` 状态；
点击某项切换筛选，再次点击当前非全部项恢复全部。触控区至少 44×44px。

Backend Device List 当前只正式支持 `page`、`page_size`，没有搜索或状态筛选参数。因此：

- “全部设备”可以展示 Backend `total`；
- 在线、运行中、离线计数只在所有分页及 Active Task 事实完整后启用；
- Search 也只在所有分页完整加载后启用，并只按正式 `display_name` 做本地匹配；
- 数据未完整时不得把当前页搜索/过滤伪装成全量结果，也不得发送自造 Query Param；
- 后续若需要服务端搜索或完整聚合统计，应作为 Backend Contract Gap 单独处理，本轮不改 Backend。

## 状态映射与设备插画

列表视觉状态优先级固定为：

1. `connection_status=offline` → 离线；
2. `connection_status=online` 且正式 Active Task `status=running` → 运行中；
3. `connection_status=online` → 在线；
4. `worker_runtime=null` → 未上报，不得归为离线。

`enabled` 独立显示为“已启用 / 已停用”，不参与在线、离线或运行中推断。Card Meta 固定为
“心跳 {相对时间} · 已启用/已停用”；列表不展示 Worker 版本或任务名称。

`DeviceStatusArtwork` 接收独立的 `kind` 与 `state`。当前 Backend 没有设备 Kind Contract，所以生产列表
统一使用 desktop fallback；不得依据名称、位置或 Worker 信息猜 desktop/laptop/server。组件测试可覆盖
desktop、laptop、server 三种视觉容量。未来只有 Backend 提供正式字段后才能映射真实 Kind。

## Theme 与可访问性

Light / Dark 使用同一结构和几何，只切换集中语义值。System 继续解析为 Light 或 Dark，不建立第三套颜色。
Search、Summary、Card、Artwork、Header 与 Bottom Navigation 都必须在 Light / Dark 下可读；Focus、Pressed、
Reduced Motion 与 Safe Area 继续遵守既有 Foundation 规则。Metric 和整卡详情入口必须保留语义化 Button、
可见 Focus Ring 与不少于 44px 的触控命中区。

## 验收

- Visual Mock：20 台设备，覆盖运行中、在线、离线、未上报、启用/停用和长名称；
- 交互：全部/在线/运行中/离线、再次点击恢复全部、完整数据 Search、Card → Device Detail；
- 数据：部分分页禁用本地全量筛选和 Search，完整分页后启用；
- 视口：360 / 375 / 390 / 430px，Light / Dark；不同高度至少 640 / 740 / 844 / 932px；
- 滚动：Header、Controls、Bottom Navigation 位置不随 Card List 滚动；Document 不产生纵向滚动；
- 质量：Console Error = 0、Horizontal Overflow = 0、Safe Area 四向有效。
