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

Credential Read 不含密码、密文；Session Read 不含 Cookie、payload 或密文。密码只存在于 Create/Update 写请求，Update 的空字符串表示保留现有密码。Session payload 的写入目前只属于内部 Service Contract，不开放普通 Frontend Route。

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

`POST /api/v1/tasks` 创建 `yingdao.app.run` 时，input 固定为
`{"app_id":"...","params":{...}}`。店铺上下文通过独立有序 `shop_ids` 提交，不进入 input。
Backend 必须验证目标 Device 启用、全部 Shop 有效并与该 Device 存在启用 Binding、账号可用、
最新影刀 Inventory 为 ready、执行可用、已登录、App 对当前账号可见，并按已保存 Schema校验/补齐 params。

## Device Lifecycle API

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

## Task Runtime Event API

`POST /api/v1/tasks` 的 `shop_ids` 是有序的正式店铺上下文集合；需要店铺账号的即时任务必须明确
提交，但账号内容不得放进 `input`。重复 ID 被拒绝，任一 Shop 无效、停用、已移除、未与目标
Device 有效绑定或缺少可用 Credential 时整次创建失败，不静默跳过。Backend 只创建一个 Task，
`TaskRead` 返回原顺序的关系 ID。认证 Worker 调用 Claim 时，Backend 才按关系顺序读取当前启用且
平台匹配的 Credential，并在 Claim 响应的 `accounts` 数组中下发最小 Payload：
`shop_id / platform_code / login_identifier / secret / preferred_verification_channel`。
普通 Task Read/List、Runtime Event 与 Result 不返回账号明文。

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

## 资料库 Asset API

- `POST /api/v1/assets`：单文件 multipart 上传，只接受真实 JPEG、PNG、WebP 内容，受 Backend
  配置的单文件大小限制；响应返回稳定 Asset 元数据、`media_type=image`、
  `source_type=upload` 与 SHA-256。
- `GET /api/v1/assets`：按文件名搜索并使用统一 `page/page_size` 分页。
- `GET /api/v1/assets/{asset_id}/content`：Frontend 预览与读取图片的正式接口，不暴露存储路径。
- `DELETE /api/v1/assets/{asset_id}`：只删除未被 Task 引用的图片；被引用时返回 `ASSET_IN_USE`。
- `GET /api/v1/worker/tasks/{task_id}/assets/{asset_id}`：仅允许持有现有 Worker 身份的目标设备在
  该 Task 处于 RUNNING 时下载其关联图片；其他设备、其他 Task 或非运行状态均不得读取。

HTTP Upload 只负责接收输入并调用 Asset Service。Asset Service 使用 Storage Adapter 原子保存
文件后提交数据库元数据；数据库提交失败会清理本次新文件。响应不包含 `storage_key`，任何
客户端都不得猜 Backend 文件系统路径。现有 URL 与 Worker Claim 的图片字段保持兼容，Claim
不会新增 `media_type / source_type / storage_key`。
