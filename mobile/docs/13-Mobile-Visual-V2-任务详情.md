# Mobile Visual V2 任务详情

## 1. 状态与范围

`/tasks/:taskId` 已完成 Task Detail Visual V2 的选择性迁移，当前状态为
**Completed / Candidate for Visual Review（已完成 / 候选人工视觉复核）**。

本页只提供任务事实与只读运行日志，不增加暂停、取消、重试任务、重新运行或删除等业务动作。该候选状态不等于
Frozen，也不授权修改已经冻结的 Task List、Device List、Device Detail 或 Shared Foundation。

## 2. 页面组合

```text
MobileAppShell V2
├─ MobileDetailHeader V2（返回 / 任务详情 / 无虚假 More）
├─ Detail Content
│  ├─ TaskDetailCard
│  │  ├─ TaskDetailSummary
│  │  └─ TaskDetailInfo
│  └─ TaskRuntimeLog
│     ├─ 固定 Log Header
│     └─ Internal Log Scroll
└─ MobileBottomNavigation V2（任务 Active）
```

页面根层不滚动。详情 Header、顶部任务信息卡、日志 Header 与 Bottom Navigation 保持固定；只有日志内容容器
`[data-testid='runtime-log-scroll']` 使用 `overflow-y: auto`。布局由 `100dvh` AppShell、Flex、`min-height: 0`
和四向 Safe Area 自然分配，不写死参考 HTML 的宽高或绝对定位。

## 3. 已复用的 Frozen Visual V2

- `MobileAppShell V2`：连续 Page Background 与 Safe Area 所有权。
- `MobileDetailHeader V2`：返回、居中标题和右侧 Action Slot；本页没有真实 Action，因此 Slot 为空。
- `MobileBottomNavigation V2`：五入口顺序与 Task Active 状态。
- Visual V2 Typography、Business Card Surface、Divider、Status 与 Light / Dark Semantic Token。
- Task Status Registry、Task Status Artwork Resolver 与 Mobile Icon Registry。
- Task / Device Entity 的正式 DTO、Query 与统一 API Client。

`TaskListCard` 已经 Frozen，包含列表 Chevron、整卡导航、122px Geometry 与列表 Tag 语义。详情页没有 Chevron 或
列表点击行为，因此不强制复用完整 `TaskListCard`；`TaskDetailSummary` 只复用其底层 Artwork、状态、字体、颜色与
Surface 语言，避免改变 Task List DOM、Geometry 或 Device Detail Current Task。

## 4. Task Detail Card

顶部在视觉上是一张 Surface，代码职责保持两部分：

- `TaskDetailSummary`：正式执行名称、状态 Artwork、状态文案及可可靠计算时的运行时长。
- `TaskDetailInfo`：按真实字段动态生成 Key / Value 行。

Summary 与 Info、Info 各行之间只使用 Frozen V2 Divider Token。任务名称和设备名称保持单行省略，避免在
360px 下挤压结构；完整事实仍保留在原始 DTO，不以 Raw ID 代替用户可读名称。

### Summary 数据来源

| UI 内容  | 正式来源                                   | 规则                                                                  |
| -------- | ------------------------------------------ | --------------------------------------------------------------------- |
| Title    | `TaskReadDto.execution_display_name`       | 使用现有执行名称防御性回退，不在页面维护名称表                        |
| Artwork  | `TaskReadDto.status`                       | `running / pending / failed+lost / success` 使用正式 Artwork Registry |
| Status   | `TaskReadDto.status`                       | 使用 `TASK_STATUS_META` 唯一中文映射                                  |
| Duration | `started_at`、`finished_at` 与状态         | 只有时间戳可可靠计算时显示；运行态使用本地轻量时钟                    |
| Tags     | 当前详情 DTO 无正式 Provider / Display Tag | 省略，不为视觉对称伪造                                                |

## 5. TaskDetailInfo 字段

| 候选字段 | 状态                   | 正式来源与展示规则                                                                       |
| -------- | ---------------------- | ---------------------------------------------------------------------------------------- |
| 开始时间 | Supported              | `TaskReadDto.started_at` 非空时显示，并复用 Mobile 时间格式工具                          |
| 执行设备 | Supported              | `target_device_id` 只用于 `GET devices/{deviceId}`；UI 显示 `DeviceReadDto.display_name` |
| 触发方式 | Omitted                | 当前 Task Detail Contract 无 Trigger / Schedule Relation，不从名称或 Input 猜测          |
| 执行账号 | Omitted                | 当前 Contract 无 Provider Account / Runtime Account / Operator，不显示 Prototype Mock    |
| 执行结果 | Supported when present | 仅成功任务的非空 `result.summary`；不通用展开 Result 或 Input                            |
| 失败原因 | Supported when present | 仅失败或丢失任务的非空、已脱敏 `error_message`；不把 `error_code` 暴露为普通 UI          |

Device Query 与 Task Query 独立。Task 成功后页面立即显示；Device 加载或失败只影响“执行设备”这一行，分别使用
“加载中”与“暂时无法加载”，不得阻塞 Task Card 或 Runtime Log。

## 6. Runtime Logs Contract

日志继续复用正式 `useTaskRuntime` 与 Task Event API：

- 真实字段为 `seq`、`event_type`、`level`、`message`、`event_at`、`metadata` 等正式 DTO 字段。
- API 语义为按 `seq` 升序；客户端按 `seq` 去重，早期日志使用 `before_seq`，增量使用 `after_seq`。
- UI 只显示未改写的 `message` 与格式化后的 `event_at`。Contract 没有 Title / Description 时不得拆造两层文案。
- Timeline Dot 只按正式 `event_type` 映射：`status/progress` 为 Info、`completed` 为 Success、`failed` 为
  Danger、`log` 为 Neutral；不得从消息文本推断等级。
- 日志始终按纯文本渲染，不解析 HTML。

日志 Header 固定在 Panel 内部滚动区之外。首次无数据时显示局部 Loading；Task 存在且 Events 成功为空时显示
“暂无运行日志”；首次失败显示“加载失败 / 重试”。已有 Event 时的增量失败保留旧内容并显示局部“刷新失败 /
重试”，不会把整个详情切回 Loading 或 Error。

## 7. Header 与返回

- 普通从 Task List 进入时，返回 `/tasks`。
- 从 Device Detail Current Task 进入时，继续读取既有 `fromDeviceId` Query 并返回对应
  `/devices/:deviceId`，不新增第二套来源协议。
- Theme 只使用现有 Light / Dark / System Store。
- 当前没有正式 Task Action Contract，Header 不显示 More，也不提供 Fake Menu。

## 8. Prototype Gaps

参考 HTML 中下列内容没有迁移为 Production 事实：

- Fake Device、每日触发时间、影刀执行账号与 Mock Tags。
- 固定的“2小时32分钟”等 Fake Duration。
- Mock Log、拆分出的 Log Title / Description 与从文案推断的事件等级。
- Preview Phone、状态栏、Home Indicator、独立 Theme LocalStorage、内联 SVG 字符串和固定绝对布局。

当前 Backend Contract Gap 是：Task Detail DTO 不提供 Device Display Name 内嵌字段、Trigger / Schedule
Relation、Provider / Runtime Type、Application / Skill Display Tag、Provider Account 或 Operator。Device Display
Name 已通过既有只读 Device Detail Query 补充；其余字段全部省略，本 Feature 不修改 Backend。

## 9. 响应式、主题与回归

正式回归矩阵覆盖 360×640、375×740、390×844、428×926、430×932 的 Light / Dark。必须验证：

- Task / Device 长名称单行省略且不造成横向溢出。
- Task Card 固定在内容顶部；Log Panel 获得剩余高度，只有 Log Body 可滚动。
- Log Header 与 Bottom Navigation 不被日志滚动带走或遮挡。
- Console Error 与 Horizontal Overflow 均为 0。
- Light / Dark 只消费 Frozen Visual V2 Semantic Token。
- Task List V2、Device List V2、Device Detail V2、Bottom Navigation、Page Background 与 Typography 无非预期变化。

## 10. 候选边界

本次候选范围是 Task Detail Composition、`TaskDetailCard`、`TaskDetailSummary`、`TaskDetailInfo` 与
`TaskRuntimeLog` 的 Visual V2 表达和内部滚动契约。它们尚未 Frozen；完成人工视觉确认后才能进入冻结与
Integration Gate。任何后续修改仍须保护现有 Frozen Shared Foundation 与 Task / Device 页面。
