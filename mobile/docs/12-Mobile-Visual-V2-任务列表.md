# Mobile Visual V2 任务列表

## 状态与范围

`/tasks` 当前状态为 **Completed / Candidate for Visual Review（已完成 / 候选人工视觉复核）**。
本规范记录 Task List Visual V2 的正式组合、真实 Backend 映射和视觉候选边界；不冻结页面，不迁移
Task Detail，也不开放 Device List / Detail 已冻结的 Geometry、Navigation 或 Scroll Contract。

参考源是用户提供的 `任务卡.html`。只迁移其信息层级、比例、密度和移动端列表方向；不迁移假手机状态栏、
固定 390×844 外壳、CDN 资源、Mock DTO、固定顶部像素、固定底部像素或原型路由。生产继续使用 Vue Router、
TanStack Vue Query、正式 Entity DataSource、现有 Theme Store、`100dvh` 与四向 Safe Area。

## Task List Composition（任务列表组合）

```text
MobilePageHeader V2
→ MobileSearchField V2
→ MobileSummaryStrip V2
→ MobileListContextCard V2
→ Task List（唯一主滚动区）
→ MobileBottomNavigation V2
```

- Header 标题为“任务”；左侧 Hamburger 只打开运行日期 Vant Popup。
- Theme Toggle / Bell、连续 Page Background、Bottom Navigation 与 Safe Area 复用 Frozen Foundation。
- Search 直接进入 Backend 正式 `search` 参数；不在已加载数组做伪服务端搜索。
- Header、Search、Summary、Context 与 Bottom Navigation 不随 Task Card 滚动；Document 不承担业务滚动。

## Date Filter（运行日期筛选）

默认“近7天”，即当前本地自然日加前6日。快捷项固定为“今天 / 昨天 / 近7天 / 全部”；指定日期是单日
`input[type=date]`，不实现 Range Picker。今天、昨天、近7天和指定日期都转换为本地自然日开始到下一日开始
的半开区间；“全部”同时省略 `created_from` 与 `created_to`。

Context Date Label 固定使用“今天 / 昨天 / 近7天 / 全部 / M月D日”。日期、Search、Metric 与 Context
消费同一筛选状态，禁止页面再维护一份显示态。

## Metric Mapping（指标映射）

顺序固定为：运行中、待运行、异常、已完成。

| Metric | 正式状态        | 数量来源                                                 |
| ------ | --------------- | -------------------------------------------------------- |
| 运行中 | `running`       | `GET tasks?page=1&page_size=1&status=running` 的 `total` |
| 待运行 | `pending`       | `status=pending` 的正式 `total`                          |
| 异常   | `failed + lost` | 两个正式 `total` 相加                                    |
| 已完成 | `success`       | `status=success` 的正式 `total`                          |

Backend 没有 Stats API 且一个列表请求只接收一个状态，因此当前需要五条轻量 Total Query。任一必要 Total
不可用时显示 `—` 并禁用对应 Metric，不允许使用 Current Page Length。点击 Metric 切换对应筛选；再次点击
当前 Metric 恢复全部。异常列表由 FAILED 与 LOST 两条分页流合并、按 `created_at` 排序并按 `task_id` 去重。

## Context Card（查询上下文卡）

Shared Candidate 为 `MobileListContextCard.vue`，只负责 `label + count + contextLabel` 排版，不知道 Task、
Status、Date 或 Query。正式候选值为 48px Min Height、15px Radius、16px Horizontal Padding，并只消费
Visual V2 Semantic Surface / Border Token。

示例：`任务 26个 · 近7天`、`运行中 8个 · 近7天`、`异常任务 3个 · 今天`、`任务 5个 · 8月31日`。
数量始终来自当前正式 Task Query `total`；FAILED + LOST 时取两条正式 Total 之和。

## TaskCard V2

TaskCard 复用 `TaskListCard.vue` 与 Frozen `MobileBusinessCardFrame.vue`，不得建立第二套 `.task-card`。

| Geometry       | 值                            |
| -------------- | ----------------------------- |
| Minimum Height | 122px                         |
| Grid           | `102px minmax(0, 1fr) 18px`   |
| Padding        | `15px 17px 15px 16px`         |
| Radius         | 17px                          |
| Status Artwork | 60px，内部 Registry Icon 30px |
| Title Gap      | 5px                           |
| Status Gap     | 5px                           |
| List Gap       | 14px                          |

三行固定为 Title → Status + Optional Duration → Contract Tags。Title 单行省略；Tag 最多两枚且不能挤压
Trailing Chevron。当前真实 DTO 只有 `skill_display_name` 可作为业务 Tag，因此正式实现最多显示这一枚；
Provider / Runtime Type 和 Application Display Name 不存在时保持缺席。

Artwork 只按正式 Task Status 解析：Running 使用 Success Semantic Token，Pending 使用 Primary，Failed / Lost
使用 Danger，Success 使用 Neutral。图标只能来自 Mobile Icon Registry；组件禁止硬编码 Hex、RGB 或 SVG Path。
Duration 只使用有效正式时间戳计算，不从日志、进度或任务名称估算。

Task List 使用 `metaMode=tags`；Device Detail Current Task 继续使用默认 `metaMode=context`，因此本迁移不会
改变设备详情的开始时间 / 设备名称行。整卡继续进入既有 `/tasks/:taskId`，不创建第二个详情 Route。

## Prototype Gaps（原型差异）

- HTML 的 Provider / RPA / Application Tag 在 Task List DTO 中不存在，未填充 Fake 数据。
- HTML 的固定统计数字、假状态栏、通知红点、CDN 图标、Home Indicator 与固定 Viewport 未迁移。
- Backend 没有 Task Stats API；五状态 Total Query 是当前只读 Contract 的明确代价，不伪造聚合接口。
- Backend 单次只支持一个 `status`；异常必须保持 FAILED / LOST 两条正式语义，不能新增 `error` 状态。

## Shared / Candidate / Frozen

继续复用的 Frozen Foundation：MobileAppShell V2、MobilePageHeader V2、MobileSearchField V2、
MobileSummaryStrip V2、MobileBottomNavigation V2、Typography V2、Page Background、Business Card Surface 与
MobileBusinessCardFrame Geometry。

本轮 Candidate：Task List Visual V2、`MobileListContextCard V2`、TaskCard V2 List Presentation
（Status Artwork / Duration / Tags）。DeviceCard、Device Detail Current Task、Bottom Navigation、Safe Area、
Router 和独立滚动契约均保持 Frozen 0 变化。只有用户完成人工 Visual Review 后才能另行提出 Freeze。

## Validation Baseline（验收基线）

- Viewport：360×640、375×740、390×844、428×926、430×932；Light / Dark。
- 无横向溢出；Metric Label 不换行；长标题和 Tag 单行省略；Bottom Navigation 不遮挡末卡。
- Header / Search / Summary / Context 固定，Task List 获得剩余高度并独立滚动。
- 覆盖默认近7天、四个日期快捷项、指定日期、Search、四项状态、取消状态、组合 Query、分页、空态、
  Initial Error / Retry、Background Error 保留旧数据和 Next Page Error / Retry。
- Device List Computed Geometry、Device Detail Current Task Geometry 与 Frozen Foundation 均为 0 非预期变化。
- 正常成功页面 Console Error = 0、Horizontal Overflow = 0；Prettier、lint、typecheck、unit、build、
  Playwright、Visual Playwright 与 `git diff --check` 全部通过。
