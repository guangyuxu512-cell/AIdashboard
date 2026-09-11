# Mobile Theme & Pull Refresh V1

## 状态与范围

Status（状态）: **Completed / Candidate for Integration（已完成 / 待集成）**

本阶段只建立 Mobile 顶部主题同步和设备、任务列表的一致下拉刷新体验；不改变已冻结的 Visual V2
Anatomy（结构）、Geometry（几何）、Navigation（导航）或 Scroll Contract（滚动约定）。

- 不修改 PC、Backend、数据库、Worker、NAS 或 Electron。
- 不修改 Device 离线正式语义：`worker_runtime = null` 继续展示“未连接”，不计入正式 Offline
  Metric（离线指标）或 Offline Filter（离线筛选）。
- Device / Task 继续只有各自既定的一个业务滚动区；Header、Summary、Toolbar 与 Bottom Navigation
  不参与内容滚动。

## Theme Chrome Contract（浏览器顶部主题契约）

`useThemeStore` 仍是唯一 Theme State（主题状态）来源。每次解析出 Light 或 Dark 后，它同步：

1. 根元素 `data-theme`、`color-scheme` 和 Vant Dark Class；
2. 唯一 `meta[name="theme-color"][data-mobile-theme-color]` 的内容；
3. Apple PWA `apple-mobile-web-app-status-bar-style`：Light 为 `default`，Dark 为
   `black-translucent`；
4. `#app` 的 `--mobile-root-background`，使实际应用根背景与 Visual V2 Page Background（页面背景）使用同一
   语义来源；`html` / `body` 保持解析主题下的 `--bg-app` 作为浏览器画布回退，避免破坏既有非 Visual V2
   页面与开发调参器的基础颜色契约。

浏览器颜色从 `tokens.css` 中的 `--mobile-browser-theme-color` 获取；业务组件不得重复写入 Hex 或自行维护
`theme-color`。Top Safe Area、Visual V2 Header 与页面背景仍由既有 Shell / Header Contract
负责，不能新增第二个顶部 Surface 或重复 Top Safe Area Padding。

Theme Store 在首次初始化、系统主题变更、`visibilitychange`、`pageshow` 与 `orientationchange` 后重新同步。
这覆盖手动 Light / Dark、System、后台恢复、关闭重开后的存储模式和横竖屏重新进入。浏览器自动化只能验证
metadata 与页面样式；iPhone Safari 和主屏幕 PWA 的真实状态栏绘制仍需发布后真机验收。

## Shared Pull Refresh Contract（统一下拉刷新契约）

`MobilePullRefresh` 是目前唯一的正式列表下拉刷新 Shared UI。它基于 Vant `PullRefresh`，不重新实现
触摸引擎；当前正式接入点仅为：

- Device List；
- Task List。

其它页面没有真实刷新入口时不得为了统一而伪造 Refresh API。Shared 层拥有手势状态、渐进阻尼提示、终态反馈、
重复触发保护、减少动态效果与可选震动；页面 / Feature 只传入返回真实成功或失败结果的异步刷新方法，并继续拥有
Query、分页、搜索、筛选与业务数据状态。

统一交互时间基线：

| 阶段                         | 基线   |
| ---------------------------- | ------ |
| 最短 Loading（加载）可见时间 | 350ms  |
| Success（成功）反馈          | 500ms  |
| Error（失败）反馈            | 1200ms |
| 回弹动画                     | 220ms  |

请求在松手后立即发起，不通过延迟网络请求制造停顿。未到阈值显示“下拉刷新”并平滑收回；达到阈值显示
“松开刷新”；请求期间显示“正在刷新”；终态显示“刷新完成”或“刷新失败”。失败保留已有列表，下一次下拉即为
重试入口，不显示技术原因或清空已成功数据。

一次手势到达释放阈值时，支持 `navigator.vibrate` 的平台最多轻震一次；不支持标准 Vibration API 的
iPhone Safari / PWA 自然降级为视觉反馈，不伪造震动。`prefers-reduced-motion: reduce` 下禁用回弹等待与震动。
组件卸载时清理计时器并忽略迟到结果，避免 Route 切换后污染新页面。

手动刷新保留当前搜索、筛选和分页意图。Device 的完整分页筛选在刷新时保留已验证的完整筛选结果，直到新的
完整结果或明确失败抵达；不得把当前页过滤冒充全量结果。后台 Query 更新不经过 `MobilePullRefresh`，因此不播放
刷新动画或触发震动。

## 验收

- Light / Dark / System 下验证 `theme-color`、根背景、透明 Visual V2 Header 与 Top Safe Area 连续性。
- Device / Task 分别验证短下拉、慢请求、成功、失败、重复手势、空列表、筛选中刷新、分页失败和路由离开。
- 继续覆盖 360 / 375 / 390 / 430px、不同高度、Console Error = 0 与 Horizontal Overflow = 0。
- 真机 Safari 与主屏幕 PWA 的状态栏、主题恢复和震动降级必须在发布后单独记录；浏览器模拟不能替代该证据。
