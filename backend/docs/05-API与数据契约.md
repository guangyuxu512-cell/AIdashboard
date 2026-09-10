# API 与数据契约

Pydantic Schema / OpenAPI 为权威来源。

原则：

- 请求/响应字段明确。
- 枚举明确。
- 错误码明确。
- 不向前端泄露数据库内部模型。
- 不把 ORM 对象直接作为长期 Contract。

统一分页、时间和错误结构。
破坏性 Contract 变化必须明确处理兼容或版本升级。

## 工程健康检查

`GET /health` 是不依赖数据库的工程级健康检查，不属于业务 API。
生产 Host Nginx 必须将精确 `/health` 转发到 Backend，不能落入 Frontend SPA fallback。

成功响应：

```json
{
  "status": "ok"
}
```

## Core Domain V1 Contract

统一前缀为 `/api/v1`：

- `/users`：GET list、GET detail、POST create、PATCH update。
- `/shops`：GET list、GET detail、POST create、PATCH update、DELETE soft remove。
- `/devices`：GET list、GET detail、POST create、PATCH update。
- `/shops/{shop_id}/device-bindings`：GET list、POST create。
- `/shops/{shop_id}/device-bindings/{device_id}`：PATCH update/disable。

列表统一返回：

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 20
}
```

错误统一返回 `code`、`message`、`request_id`、可选 `details`。V1 业务错误码包含 `USER_NOT_FOUND`、`SHOP_NOT_FOUND`、`DEVICE_NOT_FOUND`、`INVALID_DEVICE_BINDING`、`IMMUTABLE_SHOP_IDENTITY`；请求校验使用 `VALIDATION_ERROR`，数据库异常统一映射为 `DATABASE_OPERATION_FAILED`。

## Access Foundation V1 Contract

- `GET /api/v1/access/me`：返回当前请求解析后的 ActorContext。
- `GET /api/v1/access/me/teams`：返回当前 Human User 的 Team/Membership 摘要，供未来 Team
  Switcher 使用；该接口不要求先选定 Active Team。
- `X-Team-ID`：用户有多个 Active Membership 时的 Team Context Header。Header 只是选择请求，
  Backend 必须验证当前 User 拥有对应启用 Membership 且 Team 启用。

Actor DTO 只包含 `user_id / user_display_name / team_id / membership_id / role_code /
data_scope`。My Teams DTO 只包含 Team 名称和状态、Membership ID/状态、Role 与 Scope，不返回
ORM 或任何凭证字段。多 Team 未选择返回 `TEAM_CONTEXT_REQUIRED`；非成员、停用 Membership 或
停用 Team 返回 `TEAM_ACCESS_DENIED`；无 Active Membership 返回 `TEAM_MEMBERSHIP_REQUIRED`。

Human Auth V1 已为 `users` 增加可空 `login_name/password_hash`，并以服务端人员会话识别
`HumanPrincipal`。`POST /api/v1/auth/login` 建立 HttpOnly Cookie，`POST /api/v1/auth/logout`
撤销当前会话，`GET /api/v1/auth/me` 只返回当前人员最小摘要。现有通用 `UserRead` 不返回
`login_name/password_hash`；后续 Access Management 必须使用独立、受权限保护的管理 Contract。
`get_human_principal` 不接受可伪造的 User-ID Header；ActorContext、Team 选择与既有 Access API
Contract 保持不变。

## Access Management V1 Contract

统一前缀为 `/api/v1/access-management`。`GET /me/module-access` 需要有效的 Human
ActorContext，返回当前选中 Membership 的 `module_codes` 和
`is_access_administrator`，不返回 User、Team、密码或会话内部字段。

以下人员、Team 与 Membership 管理接口均要求当前选中 Membership 的
`role_code=access_admin`：

- `GET/POST /members`：分页查询（可按显示名或登录账号 search）与创建人员。
- `GET/PATCH /members/{user_id}`：读取人员管理视图、启用或停用人员。
- `POST /members/{user_id}/password`：重置密码并撤销该人员全部 Human Session。
- `POST /members/{user_id}/memberships`、`PATCH /memberships/{membership_id}`：新增或更新
  Team Membership、数据范围、启用状态、角色与模块访问。
- `GET/POST /teams`、`PATCH /teams/{team_id}`：读取、创建和更新 Team；不提供 Hard Delete。

历史 `/api/v1/users` Core Domain 路由也改为 `access_admin` 才可调用，防止它成为新人员管理边界的
绕过入口；PC 管理端必须使用上列 Access Management Contract，不以旧 `UserRead` 管理登录凭据或
Membership。

人员创建请求只在写入期接收 `password`，响应的人员、Membership 与 Team DTO 永不包含密码、
Password Hash、Cookie 或 Session Token。管理角色只有 `member` 和 `access_admin`；模块代码只能
是当前 PC Module Registry 的 `shop / asset / ai-workbench / device / task / schedule / settings`，
不接受 development-only `foundation` 或未知值。模块代码重复、未知角色及空 PATCH 均由
`VALIDATION_ERROR` 拒绝。

管理边界失败使用 `HUMAN_AUTHENTICATION_REQUIRED`、
`ACCESS_ADMINISTRATION_FORBIDDEN`、`MODULE_ACCESS_DENIED`、
`LAST_ACCESS_ADMINISTRATOR_REQUIRED`、`TEAM_DISABLED`、`TEAM_MEMBERSHIP_CONFLICT` 等正式错误码。
资料库、Device、Task 与 Schedule 的全部 Human 路由分别执行 `asset`、`device`、`task`、`schedule`
模块授权，并使用 ActorContext 的 `SELF / TEAM / ALL` 读取范围。它们的 Create DTO 不接受 Team 或
创建者；这两个 Ownership 字段只从 ActorContext 或可信 Schedule 继承。Shop、Credential、Shop
Session 与 Shop Onboarding 管理路由同样要求 Human Session、ActorContext 与 `shop` 模块访问；当前
Shop 尚未建立 Ownership Scope。Automation Application Config 要求 `device` 模块访问，Notification
Channel 管理与 Webhook 测试要求 `settings` 模块访问。Worker / Device Token 路由不使用 Human Guard。

Pydantic Create、Update、Read Schema 是正式 API Contract。Shop Device Binding 只包含
`shop_id / device_id / enabled` 与时间字段，不再包含 PRIMARY/BACKUP role。Frontend 的 GMV、
Session/自动化状态、CPU/内存、Worker 版本、当前任务和展示文本不属于这些 Read Schema。

Shop List 使用 `ShopListRead`，在 `ShopRead` 基础上增加可空 `session_status`：没有 ShopSession 时为 `null`，其余值直接来自正式 ShopSession Status，不由 Frontend 猜测。普通 List 与 Detail 默认排除 `deleted_at IS NOT NULL`；对已移除 Shop 的 GET、PATCH、Binding 与 Session 业务访问返回 `SHOP_NOT_FOUND`。`DELETE /api/v1/shops/{shop_id}` 返回 204，但数据库记录及认证事实仍保留。

带 `platform_shop_id` 的 Shop 已由平台身份识别建立。普通 `ShopUpdate` 不允许修改其 `display_name` 或 `platform`，且 Contract 本身不接受 `platform_shop_id` 更新；负责人、备注和既有 `enabled` 语义不受影响。`Shop.enabled` 不是自动化总开关。

`Shop.enabled=true/false` 分别表示店铺可/不可参与正常系统业务；当前不存在 `automation_enabled`，禁止用 `Shop.enabled` 表达自动化总开关。

## Credential / Session Metadata Contract

阶段 3A 增加：

- `GET /api/v1/shops/{shop_id}/credential`：仅返回脱敏账号、配置/启用状态、验证码渠道和更新时间。
- `POST /api/v1/credentials`、`PATCH /api/v1/credentials/{credential_id}`、`POST /api/v1/credentials/{credential_id}/disable`：写入与停用凭证。
- `GET /api/v1/shops/{shop_id}/session`：仅返回 Session 状态、版本、来源设备和时间元数据。
- `POST /api/v1/shops/{shop_id}/session/health-check`：人工执行权威只读验证，只返回身份与 Session 元数据。
- `POST /api/v1/shops/{shop_id}/session/refresh-lease`：获取可过期恢复租约和当前 `expected_version`。
- `DELETE /api/v1/shops/{shop_id}/session/refresh-lease/{lease_id}`：取消并释放当前客户端持有的租约。
- `POST /api/v1/shops/{shop_id}/session/refresh`：仅供 Electron Main 提交内存中的新 Session；Renderer 不接触 payload。
- `POST /api/v1/shop-onboarding/pdd/identity`：首次接入的 Electron Main 将内存中的 PDD Cookie
  payload 交给固定平台接口预检；只返回已验证的 `platform_shop_id / shop_display_name`，不创建任何
  Shop、Credential 或 ShopSession。

Credential Read 不含密码、密文；Session Read 不含 Cookie、payload 或密文。密码只存在于 Create/Update 写请求，Update 的空字符串表示保留现有密码。Session payload 的写入目前只属于内部 Service Contract，不开放普通 Frontend Route。

Electron Main 进行店铺接入或 Session 恢复时，从其受控的应用会话读取 HttpOnly Human Cookie 并附加当前
`X-Team-ID`；Cookie 不经过 Renderer，也不接受 Renderer 传入的 Raw Session Token。

## Device Provider Inventory Contract

阶段 3B-1A 增加最新 Provider 快照：

- `POST /api/v1/worker/provider-inventory`：Worker 认证接口，请求只含
  `provider_code` 与严格校验的 `inventory`，不接受 Body `device_id`。
- `GET /api/v1/devices/{device_id}/provider-inventories`：读取指定设备的最新 Provider
  快照。

当前正式 Provider 为 `yingdao`。影刀 Inventory 只包含状态/原因、版本、登录状态、安全账号元数据、
当前 userId、当前账号云端应用的 ID/名称/versionId/updateTime/appType/groupId 与发现时间；禁止密码、
Token、Cookie 和完整认证响应。应用数组作为外部 Provider 最新快照存入专用 JSONB，
不是通用业务 JSON，也不是中控台 Skill 注册表。

Inventory 状态使用 `not_installed / version_unsupported / starting / need_login /
interface_unreachable / ready`。`available` 与执行能力由
`execution_available / execution_version / execution_unavailable_reason` 独立表达。
本地 Discovery 无法从可验证数据得到账号类型或企业标记时，`account_type`
与 `enterprise_account` 允许为空；Worker 不得猜测或伪造这两个字段。

## Device Skill Capability Contract

- `PUT /api/v1/worker/skill-capabilities`：认证 Worker 上报本机 Skill Registry 完整快照；
  Body 只含 Descriptor 数组，不接受 `device_id`。
- `GET /api/v1/devices/{device_id}/skill-capabilities`：查询设备最后一次已知 Skill 能力。

Descriptor 固定包含
`skill_id / display_name / runtime / provider / version / classification`；分类只有
`internal | business`。Skill Capability
不等于 Provider Capability，也不等于影刀 Application。`yingdao.app.run` 是通用 Skill，
具体影刀应用由 Task `input.app_id` 选择；影刀的 9 个 Application 不注册成 9 个 Skill。

`device_skill_capabilities.classification` 是独立、可查询列。新 Worker 必须随完整快照上报；
兼容旧 Worker 时，Backend 只对现有五个已知内置 Skill 回填 `internal`，无法可靠判断的旧记录
保留 null，不能猜为 `business`。设备能力读取仍返回完整快照；普通 UI 只展示明确为
`business` 的记录。

## Automation Application Config API

- `GET /api/v1/automation-app-configs/{provider_code}/{app_id}`：读取应用参数配置，未配置返回 null。
- `PUT /api/v1/automation-app-configs/{provider_code}/{app_id}`：保存手工参数 Schema。

当前 provider 仅允许 `yingdao`。字段类型为 text/number/boolean/select；Backend 校验字段名、
重复项、选择项、默认值和类型。该 API 不读取或保存影刀 Credential。
所有读取与保存均要求 Human Session、ActorContext 与 `device` 模块访问。

`POST /api/v1/tasks` 创建 `yingdao.app.run` 时，input 固定为
`{"app_id":"...","params":{...}}`。店铺上下文通过独立有序 `shop_ids` 提交，不进入 input。
Backend 必须验证目标 Device 启用、全部 Shop 有效并与该 Device 存在启用 Binding、账号可用、
最新影刀 Inventory 为 ready、执行可用、已登录、App 对当前账号可见，并按已保存 Schema校验/补齐 params。
`shop_ids` 允许为空；只有非空集合才执行 Shop、Binding 与 Credential 校验，空集合在认证 Claim 中
返回 `accounts=[]`。

## Device Lifecycle API

- 全部 `/api/v1/devices` Human 路由要求 Human Session、`device` 模块访问与 ActorContext Scope；创建
  Device 固定归属当前 Team 与当前人员。详情、辅助 Device 查询和写入都不能用直接 ID 绕过 Scope，ALL
  也不允许跨 Team 写入。
- `PATCH /api/v1/devices/{device_id}` 的 `enabled` 是执行资格，不是在线状态。
- `DELETE /api/v1/devices/{device_id}` 返回 204，但实现为软移除；有活动任务时返回 `409 / DEVICE_HAS_ACTIVE_TASKS`。
- 已移除 Device 的列表与详情行为和 Shop 软删除一致：普通读取视为不存在。

## Worker Credential / Provisioning API

- `GET /api/v1/devices/{device_id}/worker-credential`：只返回
  `not_issued / issued / revoked` 与真实签发时间，不返回 Token、Hash、尾号或虚构使用时间。
- `POST /api/v1/devices/{device_id}/worker-credential/issue`：仅在没有有效凭证时签发；
  `token` 明文只在该次 `Cache-Control: no-store` 响应返回一次。
- `POST /api/v1/devices/{device_id}/worker-credential/rotate`：要求当前存在有效凭证，原 Hash
  立即被新 Hash 替换，旧 Token 不再通过认证；新 Token 同样只返回一次。
- `POST /api/v1/devices/{device_id}/worker-credential/revoke`：将当前凭证置为无效，不删除
  Device；之后 Worker Heartbeat、Poll、Capability Sync 均认证失败。
- `GET /api/v1/worker/provisioning`：首次 GUI 配置专用。只携带 Bearer Worker Token，Backend
  从 Token Hash 解析该 Token 自己的 Device ID、显示名称和启用状态；不接受客户端声明
  Device ID，也不能解析其他设备身份。其余 Worker API 仍必须同时使用 Bearer Token 与
  `X-Device-ID`。

Backend 永远只保存 Token Hash。Frontend 不提供旧 Token 读取；明文只在签发/轮换的短生命
周期 Dialog 中存在，不进入 Query Cache。

## Business Skill Catalog API

- `GET /api/v1/devices/{device_id}/business-skills`：返回指定 Device 最近一次 Worker Snapshot 中
  `classification=business` 的 Skill Catalog；Internal Skill 不进入该接口。
- Catalog 项至少包含稳定 Skill ID、显示名、版本、Runtime、Provider、分类、可用性状态和经
  Backend 规范化的 Input Schema。它不返回 Python 源码、安装包或动态执行入口。
- `input_schema` 唯一来源是 Worker Business Skill 的 Pydantic Input Model。旧 Worker 未上报
  Schema 时正常返回 `schema_unavailable`，不得 500；复杂或超出支持边界的 Schema 返回
  `schema_unsupported`。调用方不得自行猜参数。

Catalog 是 Device Scope：不同设备可以拥有不同 Business Skill 和版本。它只表达最后已知能力；
Device 是否在线、启用以及 Task 是否可创建仍由 Task Guard 在保存和触发时判断。

## Notification Channel API

- `GET/POST /api/v1/notification-channels`
- `PATCH /api/v1/notification-channels/{channel_id}`
- `POST /api/v1/notification-channels/{channel_id}/test`

Read Contract 只返回 `webhook_configured`，永不返回 Webhook URL 或密文。Update 的空 Webhook 表示保留原 Secret；测试消息由 Backend 投递。
所有读取、配置与测试均要求 Human Session、ActorContext 与 `settings` 模块访问。

## Task Runtime Event API

全部 `/api/v1/tasks` Human 路由要求 Human Session、`task` 模块访问与 ActorContext Scope；即时创建
Task 固定归属当前 Team 与当前人员，且目标 Device 与关联 Asset 必须在该 Team。`GET /events` 在读取
事件前先以相同 Scope 查询 Task。Schedule 生成的 Task 继承 Schedule 的 Team 与业务发起人。

`POST /api/v1/tasks` 的 `shop_ids` 是有序的正式店铺上下文集合，也可显式为 `[]`；需要店铺账号的
即时任务必须明确提交非空集合，但账号内容不得放进 `input`。重复 ID 被拒绝。仅非空集合中任一
Shop 无效、停用、已移除、未与目标 Device 有效绑定或缺少可用 Credential 时整次创建失败，不静默
跳过。Backend 只创建一个 Task，`TaskRead` 返回原顺序的关系 ID。认证 Worker 调用 Claim 时，Backend
才按关系顺序读取当前启用且平台匹配的 Credential，并在 Claim 响应的 `accounts` 数组中下发最小 Payload：
`shop_id / platform_code / login_identifier / secret / preferred_verification_channel`。
无店铺上下文的 Claim 返回 `accounts=[]`。普通 Task Read/List、Runtime Event 与 Result 不返回账号明文。

同一创建接口的 `asset_ids` 是可空、有序且不可重复的图片关系集合。Backend 必须一次验证全部
Asset 存在，并仍只创建一个 Task；不得按 Shop 或图片拆分任务，也不得把 Base64、服务端文件
路径或永久下载 URL 写入 `input`。`TaskRead.asset_ids` 只返回关系 ID。Worker Claim 的 `assets`
按原顺序返回 `asset_id / filename / position / content_type / size_bytes / sha256 / download_path`；
无图片时该数组为空。下载路径是短期运行信息，不写回 Task JSON。

- `GET /api/v1/tasks`：管理端 Task 分页列表，支持
  `status / device_id / search / created_from / created_to`；时间语义固定为基于
  `Task.created_at` 的 `[created_from, created_to)`，两个时间参数都必须带时区。search 只覆盖
  Task ID、创建时固化的 `execution_display_name` 与 `skill_id`。默认按
  `created_at DESC, task_id DESC` 稳定排序，不改变 Worker Claim 的升序执行规则。
- `POST /api/v1/worker/tasks/{task_id}/events`：Worker Bearer Token + `X-Device-ID`
  认证的事件批量写入；认证设备必须等于 Task target，重复 `(task_id, seq)` 幂等忽略。
- `GET /api/v1/tasks/{task_id}/events`：不传游标时读取最近的有限窗口；`before_seq` 向历史方向
  加载，`after_seq` 向实时方向增量读取，两者互斥。所有响应按 seq 升序，`limit` 服务端上限
  为 200，不允许一次返回完整历史。
- `POST /api/v1/tasks/runtime-events/purge-expired`：按当前 Backend Retention 配置立即清理已
  过期 Terminal Task 的 Runtime Event，返回 `cutoff / tasks_purged / events_deleted`；不得
  接收任意日期，也不删除 Task。
- `GET /api/v1/tasks/active/{device_id}`：返回设备当前 PENDING/RUNNING Task 摘要；没有时 204。
  摘要包含创建 Task 时固化的 `execution_display_name`，不得要求 Frontend 按 app_id 发起
  N+1 Application Detail 请求。

事件 message 和 metadata 在 Worker 与 Backend 双层脱敏。设备主列表与 Inventory 等辅助
查询保持独立，活动 Task 摘要失败不得改变 Device 主数据成功语义。

Task 列表项只返回当前页展示所需摘要：Task/设备身份、状态、执行名称、Skill 展示名、
结构化 progress、当前安全消息和时间。它不返回完整 `task_events`。最新 progress/status/log
通过单页摘要 SQL 取得，禁止每行再请求 Device、Application 或 Events；完整事件只在打开
Task Runtime Drawer 后继续通过 `after_seq` 接口读取。软删除 Device 仍保留物理记录和历史
显示名，历史 Task 查询不得因此失败。

Task Detail 的 `runtime_events_purged_at` 为可空清理标记。Event 为空且标记为空表示从未产生
日志；Event 为空且标记非空表示历史日志已清理；标记非空但仍有 Event 表示清理后存在晚到
事件，调用方应展示“部分历史已清理”并继续显示现存 Event。

## Schedule API

全部 `/api/v1/schedules` 路由要求 Human Session、`schedule` Module Access 与 ActorContext Scope。
Create 不接收 Team 或创建者；Backend 从 ActorContext 保存 Ownership。`schedule_type` 只能为
`once / daily / weekly`：一次性规则要求 `local_date` 且 `weekdays=[]`，每日规则要求
`local_date=null` 且 `weekdays=[]`，每周规则要求 `local_date=null` 与不重复的 ISO weekday
数组（`1=周一` 至 `7=周日`）。`local_time` 不含 offset，`timezone` 是 IANA ID，`next_run_at` 是
Backend 计算的 UTC Instant。

`GET /api/v1/schedules` 在既有 `enabled / device_id / search / page / page_size` 外支持成对的
`occurrence_date=YYYY-MM-DD` 和 `view_timezone=<IANA timezone>`。缺任一参数或无效时区返回 422；
筛选范围是该本地日期转换的 UTC `[start, end)`，匹配该范围内的 `ScheduleRun.scheduled_for` 或
`Schedule.next_run_at`，然后才计算 total 和 page。详情、下载及触发状态不以此参数改变。

## 资料库 Asset API

- `POST /api/v1/assets`：单文件 multipart 上传，只接受真实 JPEG、PNG、WebP 内容，受 Backend
  配置的单文件大小限制；响应返回稳定 Asset 元数据、`media_type=image`、
  `source_type=upload` 与 SHA-256。
- `GET /api/v1/assets`：按文件名搜索并使用统一 `page/page_size` 分页。
- `GET /api/v1/assets/{asset_id}/content`：Frontend 预览与读取图片的正式接口，不暴露存储路径。
- `GET /api/v1/assets/{asset_id}/thumbnail`：同一 Human Auth、`asset` Module Access 与 Asset Scope
  下的卡片缩略图接口。响应固定为 WebP，最大边长 320px；它不是下载接口，也不替代原图
  `content`。
- `DELETE /api/v1/assets/{asset_id}`：只删除未被 Task 引用的图片；被引用时返回 `ASSET_IN_USE`。
- `GET /api/v1/worker/tasks/{task_id}/assets/{asset_id}`：仅允许持有现有 Worker 身份的目标设备在
  该 Task 处于 RUNNING 时下载其关联图片；其他设备、其他 Task 或非运行状态均不得读取。

HTTP Upload 只负责接收输入并调用 Asset Service。Asset Service 使用 Storage Adapter 原子保存
文件后提交数据库元数据；数据库提交失败会清理本次新文件。响应不包含 `storage_key`，任何
客户端都不得猜 Backend 文件系统路径。现有 URL 与 Worker Claim 的图片字段保持兼容，Claim
不会新增 `media_type / source_type / storage_key`。

`content` 保持原始 MIME、原始字节、原始 SHA-256 与下载/放大查看/AI 输入语义。`thumbnail`
只服务小尺寸 UI，使用 `Cache-Control: private` 且按 `Cookie, X-Team-ID` 变化；Frontend 必须通过
统一 Axios Client 获取 Blob，不能把受保护路径直接交给普通 `<img>`。缩略图暂不可用时返回
`ASSET_THUMBNAIL_UNAVAILABLE / 503`，不改变已经成功保存的 Asset 或 AI Generation Item 状态。

## AI Workbench Backend Foundation V1 API

统一前缀为 `/api/v1/ai-workbench`，全部为 Human API，并同时要求有效 `ActorContext` 与
`ai-workbench` Module Access：

- `GET/POST /template-groups`：按 Scope 分页查询或创建模板组。
- `GET/PATCH/DELETE /template-groups/{template_group_id}`：读取、编辑或删除模板组。
- `POST /template-groups/{template_group_id}/prompt-templates`：创建提示词模板。
- `PATCH/DELETE /template-groups/{template_group_id}/prompt-templates/{prompt_template_id}`：
  编辑或删除提示词模板。
- `POST /template-groups/{template_group_id}/prompt-templates/{prompt_template_id}/duplicate`：
  复制模板并归一序列。
- `PUT /template-groups/{template_group_id}/prompt-templates/reorder`：同角色内重排模板。
- `GET/POST /product-material-groups`：按 Scope 分页查询或创建商品素材组。
- `GET/PATCH/DELETE /product-material-groups/{material_group_id}`：读取、编辑或删除商品素材组。
- `POST /product-material-groups/{material_group_id}/assets` 与
  `DELETE /product-material-groups/{material_group_id}/assets/{asset_id}`：建立或解除 Asset 关系。
- `PUT /product-material-groups/{material_group_id}/template-bindings/{mode}`：按模式原子替换有序模板绑定。

列表复用 `Page[T]`、`page` 与 `page_size`；TemplateGroup 和 ProductMaterialGroup 的 Ownership
只从 ActorContext 写入，Create/Update DTO 不接受 Team、Creator 或 Data Scope。Asset 关系通过
现有 AssetService Scoped Lookup 校验；不存在、不可读或错误 Team 均返回
`ASSET_NOT_FOUND / 404`。模板组仍被 Binding 引用时返回
`TEMPLATE_GROUP_IN_USE / 409`。其余 AI 管理领域错误沿用统一 `AppError` Envelope，包括
`TEMPLATE_GROUP_NOT_FOUND`、`PROMPT_TEMPLATE_NOT_FOUND`、
`PRODUCT_MATERIAL_GROUP_NOT_FOUND`、`TEMPLATE_SEQUENCE_INVALID`、
`TEMPLATE_BINDING_INVALID` 与 `MATERIAL_ASSET_ROLE_INVALID`。

商品素材组详情中的 Asset 使用现有安全 `AssetRead` 投影，不返回 `storage_key`、bucket、绝对路径、
厂商 URL 或 Storage 凭据。本阶段没有 GenerationJob、Provider、Queue 或 Worker API。
