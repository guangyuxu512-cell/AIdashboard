# Backend 契约使用规范

## 1. 权威来源

Mobile 不自行定义 Backend 事实。实现 Entity API/DataSource 前必须依次检查：

1. `backend/app/modules/<domain>/api.py` 的方法与 URL。
2. `backend/app/modules/<domain>/schemas.py` 的 Pydantic DTO。
3. 对应 `enums.py`、`exceptions.py`、Service 与测试。
4. `backend/docs/05-API与数据契约.md` 及运行时 OpenAPI。
5. PC Frontend 已有 Mapper 只能帮助理解，不能覆盖 Backend Contract。

Backend Pydantic/OpenAPI 始终是最终权威。Contract 不存在时停止实现并报告 Contract Gap。

## 2. 已确认的通用契约

- 业务 API 前缀：`/api/v1`。
- 分页查询：`page` 默认 `1`、最小 `1`；`page_size` 默认 `20`、范围 `1..100`。
- 分页响应字段：`items`、`total`、`page`、`page_size`。
- 统一错误字段：`code`、`message`、`request_id`，以及可选的 `details`（对象、数组或 `null`）。
- 请求校验错误为 HTTP `422` / `VALIDATION_ERROR`。
- 数据库异常统一为 HTTP `500` / `DATABASE_OPERATION_FAILED`。
- 响应使用 `X-Request-ID` 关联请求；`GET /health` 不属于业务 API。

`src/shared/api/` 只固化以上通用边界。领域 DTO 在首个真实 Mobile 用例出现后，按对应 Backend Schema 建立；不得复制与当前用例无关的整份 OpenAPI。

## 3. 已存在的领域 API

以下只记录 Backend Auditor 已核对的真实范围，不代表 Mobile 当前已经接入或拥有使用权限。

| Domain              | 真实 API 范围                                                                         | 主要状态/语义                                                                                       |
| ------------------- | ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Human Auth / Access | `/api/v1/auth/*`、`/api/v1/access/me/*`、`/api/v1/access-management/me/module-access` | HttpOnly Session、Team Membership、Actor Context、Module Access                                     |
| User                | `/api/v1/users` 的列表、详情、创建、更新                                              | `enabled`；业务人员实体，不是 Mobile Session Token                                                  |
| Shop                | `/api/v1/shops` 的列表、详情、创建、更新、软移除及设备绑定                            | `platform = douyin \| pdd`；Session 状态为 `not_configured/captured/valid/invalid/refresh_required` |
| Device              | `/api/v1/devices` 的列表、详情、创建、更新、软移除及能力查询                          | Runtime 连接状态为 `online/offline`；Worker Credential 管理属于敏感能力                             |
| Task                | `/api/v1/tasks` 的列表、详情、事件、活动任务与创建                                    | `pending/running/success/failed/lost`；不存在 cancel/retry API                                      |
| Schedule            | `/api/v1/schedules` 的列表、详情、运行记录、创建、更新、软删除                        | PC 计划支持 `once/daily/weekly`，触发结果为 `task_created/blocked`；`server_selection` 的 `hourly/daily` 与 `selection_run` 属于独立选品契约，不是 Mobile Schedule V1 |

具体字段、查询参数和错误码必须回到各 Domain 的 Router、Schema、Enum、Exception 与测试核对，禁止仅凭本表实现。

## 4. DTO 与调用边界

推荐链路：

```text
Backend DTO
    ↓
Entity API / DataSource
    ↓（结构复杂时使用 Mapper）
Mobile Entity Model
    ↓
Feature / Page
```

- Backend Raw DTO 不应无边界扩散到所有 Page。
- Contract 足够简单时无需为了形式强建 Mapper。
- Page 禁止直接导入 Axios、共享 API Client 或拼接 `/api/v1/...`。
- Task 输入必须遵守正式 Business Skill Schema；Mobile 不得把 `input` 当作任意 JSON 构造。
- Backend 的状态合法性、设备可执行性和计划启用规则不得在 Mobile 复制实现。

## 5. Human Auth、Permission 与 Data Scope

Backend 已提供正式 Human Auth / Access Contract：

| 方法 | Path                                         | 用途                                         |
| ---- | -------------------------------------------- | -------------------------------------------- |
| POST | `/api/v1/auth/login`                         | `login_name/password`，设置 HttpOnly Session |
| POST | `/api/v1/auth/logout`                        | 撤销当前 Session，返回 204                   |
| GET  | `/api/v1/auth/me`                            | 恢复 `user_id/display_name`                  |
| GET  | `/api/v1/access/me/teams`                    | 读取当前用户的 Team Membership               |
| GET  | `/api/v1/access/me`                          | 按 `X-Team-ID` 解析 Actor Context            |
| GET  | `/api/v1/access-management/me/module-access` | 读取当前 Membership 的 `module_codes`        |

默认 Cookie 名为 `siyu_human_session`、Path 为 `/api/v1`、SameSite=Lax，Secure 按环境
配置；Mobile 只使用 `withCredentials` 发送，不读写 Cookie 内容。用户只有一个
可用 Team 时 Backend 可自动解析；多 Team 时需明确 `X-Team-ID`。Mobile 统一由
Axios Interceptor 注入当前 Team，不在 Page 层传 Header。

Frontend 的 Module Access 只控制入口和 Route 体验。真实安全边界必须使用 Backend
`require_module_access(...)` 及服务端 Data Scope。Worker Bearer Token 是 Device Identity，
Mobile Human Authentication 不得复用 Worker Token。

当前 Device 与 Task 的列表、详情和从属只读接口均已注入对应 Module Access 与
`ActorContext`。Backend 依据 Membership 的 `SELF | TEAM | ALL` 执行查询范围；Task Runtime Events
在返回前复用同一 Task 可读性检查。跨 Team 资源使用领域 `404`，不得由 Mobile 拉取全量后本地过滤。

## 6. Task Center V1 已冻结只读契约

Entity 通过 `shared/api` 的 base URL 使用以下相对路径：

| 方法 | 相对路径                 | 查询参数                                                                |
| ---- | ------------------------ | ----------------------------------------------------------------------- |
| GET  | `tasks`                  | `page`、`page_size`、`status`、`device_id`、`search`、`created_from/to` |
| GET  | `tasks/{task_id}`        | 无                                                                      |
| GET  | `tasks/{task_id}/events` | `after_seq` 或 `before_seq`（互斥）、`limit`（1..200，默认 100）        |
| GET  | `devices`                | `page`、`page_size`                                                     |
| GET  | `devices/{device_id}`    | 无                                                                      |

- Task 状态仅为 `pending/running/success/failed/lost`。
- 列表 DTO 提供安全的 `progress`、`current_message`、`device_display_name`；详情 DTO 不提供这三项。
- Event 响应按 `seq` 升序，返回 `next_after_seq`、`next_before_seq`、`has_more_before`；事件与 `runtime_events_purged_at` 共同判断保留状态。
- 结构化进度 Event 的 `metadata.current/total` 只有同时满足以下规则才可展示：`current` 为非布尔整数且大于等于 0；`total` 为 `null`，或为大于 0 的非布尔整数且 `current <= total`。任一字段无效时整条进度无效，禁止纠正、截断或解析日志补值。
- 当前信息只按 `progress → status → log` 的类型优先级，从各类型最新非空消息中选择；`completed/failed` 不获得 Mobile 自定义优先级。
- Device 只有服务端分页；Mobile 不得把前 100 条当作完整设备集合。详情深链必须调用 Device Detail 获取显示名称。
- `created_from/created_to` 是本地自然日转换后的半开区间；“全部时间”必须同时省略两者，禁止发送空字符串或开放区间的一端。
- V1 只读，不调用 Task create，也不存在 Mobile cancel/retry/delete 行为。
- `result` 只允许读取非空字符串 `summary`；`input` 与其他结果字段不得通用渲染。
- `error_message` 与 `error_code` 仅按 Backend 已脱敏响应展示，Mobile 不解析内部错误或复制状态机。

### Task List Visual V2 查询与 Contract Gap

`GET tasks` 正式支持 `page`、`page_size`、单个 `status`、`device_id`、`search`、
`created_from` 与 `created_to`。Visual V2 只使用 `search`、日期半开区间和以下状态映射：

| Mobile 筛选 | Backend 查询                          |
| ----------- | ------------------------------------- |
| 运行中      | `running`                             |
| 待运行      | `pending`                             |
| 异常        | `failed` 与 `lost` 两条正式查询流合并 |
| 已完成      | `success`                             |

- Backend 当前没有 Task Stats / Summary API，也不支持一个请求传多个状态。四项 Metric 因此分别使用
  `page=1&page_size=1` 读取正式 `total`；异常为 `failed.total + lost.total`，不可用时显示 `—`，不得回退为
  当前页数组计数。
- 异常列表分别分页读取 `failed` 与 `lost`，按正式 `created_at` 合并去重；Context Card 数量同样为两条
  查询的正式 `total` 之和。Mobile 聚合只属于 View Model，不改变 Backend Enum。
- 默认“近7天”表示当前本地自然日加前6个自然日；指定日期转换为该日开始到下一日开始的半开区间；
  “全部”同时省略 `created_from` 和 `created_to`。
- Task List DTO 不含 Provider Type、Runtime Type、Application ID 或 Application Display Name。列表 Tag 只能
  使用真实存在的 `skill_display_name`；原型中的 Provider / RPA Tag 属于 Contract Gap，不得猜测或从名称推断。
- Duration 只在正式 `started_at` 与 `finished_at`（或 Running 的当前时间）形成有效正区间时显示；不能从
  `current_message`、Event 文本或状态估算。

## 7. Device Center V1 已冻结只读契约

Device Center 只经 Entity API 和 `shared/api` 读取以下正式接口：

| 方法 | 相对路径                                   | 参数/响应                                                     |
| ---- | ------------------------------------------ | ------------------------------------------------------------- |
| GET  | `devices`                                  | `page`、`page_size`；`Page[DeviceRead]`，按 `created_at DESC` |
| GET  | `devices/{device_id}`                      | `DeviceRead`；不存在或已软移除为 `DEVICE_NOT_FOUND`           |
| GET  | `tasks/active/{device_id}`                 | `ActiveTaskSummaryRead`；已知设备无活动任务为 204 无 Body     |
| GET  | `devices/{device_id}/provider-inventories` | `DeviceProviderInventoryRead[]`，无分页                       |
| GET  | `devices/{device_id}/skill-capabilities`   | `DeviceSkillCapabilityRead[]`，无分页                         |

### Device 与 Runtime

`DeviceRead` 的正式字段为 `device_id`、`display_name`、`enabled`、`location`、
`note`、`deleted_at`、`worker_runtime`、`created_at`、`updated_at`。
`worker_runtime` 可为 `null`；非空时包含 `device_id`、`worker_version`、
`connection_status = online | offline`、`last_seen_at`、`started_at`、`updated_at`。

- `enabled` 只表示能否承接新 Task，不等于在线；停用设备仍可能真实在线。
- `worker_runtime=null` 表示没有 Runtime 记录，不得猜成 offline。
- Mobile 直接展示 Backend 持久化的 `connection_status`。心跳默认 15 秒、在线超时默认 45 秒、离线协调默认 10 秒都属于 Backend 可配置实现，API 不返回当前阈值；Mobile 禁止用 `last_seen_at` 重算状态。
- `last_seen_at` 只用于显示最后心跳时间，DTO 不提供 `offline_since`。

### 当前任务

活动任务仅为 `pending | running`，字段为 `task_id`、`target_device_id`、`skill_id`、
`execution_display_name`、`status`、`started_at`、`created_at`、`latest_event`。存在多条时
Backend 按 `created_at ASC, task_id ASC` 返回最早一条；`latest_event` 复用正式 Task Event DTO。

该接口不验证 Device 是否存在，因此只有在 Device List/Detail 已确认设备有效后，204 才能解释为“空闲”。列表没有批量 Current Task API，Mobile 对可见设备独立查询；辅助请求失败不能覆盖 Device 主查询成功状态。点击活动任务必须进入现有 `/tasks/:taskId`，不得复制 Task DTO、状态映射或详情页。

### Provider 与 Skill 快照

Provider Inventory 当前只有 `provider_code = yingdao`。外层字段为 `device_id`、
`provider_code`、`available`、`provider_version`、`account_display`、`account_type`、
`enterprise_account`、`last_discovered_at`、`inventory`、`updated_at`。
影刀 `inventory.status` 仅允许：

```text
not_installed | version_unsupported | starting | need_login |
interface_unreachable | ready
```

`available`、`status`、`execution_available`、`logged_in` 是不同事实；原因、版本和账号按
正式 DTO 展示，`applications` 只取正式数组长度作为摘要。200 `[]` 表示 API 没有可返回快照，不能解释为 Provider 正常或异常。快照在 Worker 离线后仍保留，且 Contract 没有 freshness TTL。

Skill Capability 字段为 `device_id`、`skill_id`、`display_name`、
`runtime = python | rpa | discovery`、`provider`、`version`、
`classification = internal | business | null`、`input_schema`、`updated_at`。
`classification=null` 是正式兼容状态，不能猜成 business。Skill 快照不代表 Device 在线、启用、Provider ready 或可创建 Task；V1 只在详情按 business/internal/unclassified 计数。

### 查询与 Contract Gap

- Device List 只支持 `page/page_size`，没有 `connection_status`、Active Task 状态、搜索或等价服务端
  筛选参数；这是 Device 快捷筛选的正式 Contract Gap。Mobile 不得发送自造参数，也不得把当前分页
  的本地过滤冒充完整筛选。只有 Infinite Query 已加载全部 Backend 页，且相应连接/Active Task 事实
  已完整确认时，才允许渲染 Device 快捷筛选结果；入口可在首屏成功后触发按正式 `page/page_size` 的
  可控补齐，并必须明确展示准备、失败和重试状态。
- Provider 与 Skill 只在详情加载，列表不发出大数组 N+1 请求。
- Backend 没有 Device + Current Task + Provider + Skill 聚合接口，也没有 Current Task 批量接口。
- Backend 没有正式 Device Kind / Form Factor 字段；Production Device Artwork 只能使用统一 desktop
  fallback，不得按 `display_name`、location、Worker Version 或 Provider 猜 desktop/laptop/server。
- `worker_runtime=null` 仍表示 Contract 事实缺失而非 Backend 离线判定。Visual V2 的独立 Connection Display
  Meta 使用 `unreported` 并显示“未连接”，不得回写 DTO、参与 Backend Offline 统计/筛选或声称 Backend
  返回了 offline；Frozen Artwork 仍使用既有 offline fallback，且不得扩展第四个 Artwork State。
- Provider/Skill 的空数组无法区分“从未上报”和“明确上报空快照”；Provider 没有 freshness 标记。
- Human Auth、Team Context、Module Access 及 Device / Task 的 Actor Context Data Scope 已在 Backend
  正式收口；真实 PostgreSQL 与 Browser E2E 必须持续验证无模块权限为 `403`、跨 Team Device / Task /
  Runtime Events 不泄露资源。Mobile 入口隐藏仍只属于体验边界，不能替代 Backend Guard。
- V1 不调用 Device 创建、更新、移除、绑定、Credential、Task 创建或任何 Worker 写接口，Backend 本轮不修改。
