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

Pydantic Create、Update、Read Schema 是正式 API Contract。Frontend 的 GMV、Session/自动化状态、CPU/内存、Worker 版本、当前任务和展示文本不属于这些 Read Schema。

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
`{"app_id":"...","params":{...}}`。Backend 必须验证目标 Device 启用、最新影刀 Inventory
为 ready、执行可用、已登录、App 对当前账号可见，并按已保存 Schema 校验/补齐 params。

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

## Notification Channel API

- `GET/POST /api/v1/notification-channels`
- `PATCH /api/v1/notification-channels/{channel_id}`
- `POST /api/v1/notification-channels/{channel_id}/test`

Read Contract 只返回 `webhook_configured`，永不返回 Webhook URL 或密文。Update 的空 Webhook 表示保留原 Secret；测试消息由 Backend 投递。

## Task Runtime Event API

- `POST /api/v1/worker/tasks/{task_id}/events`：Worker Bearer Token + `X-Device-ID`
  认证的事件批量写入；认证设备必须等于 Task target，重复 `(task_id, seq)` 幂等忽略。
- `GET /api/v1/tasks/{task_id}/events?after_seq=<n>&limit=<n>`：只返回 seq 大于游标的有限事件。
- `GET /api/v1/tasks/active/{device_id}`：返回设备当前 PENDING/RUNNING Task 摘要；没有时 204。
  摘要包含创建 Task 时固化的 `execution_display_name`，不得要求 Frontend 按 app_id 发起
  N+1 Application Detail 请求。

事件 message 和 metadata 在 Worker 与 Backend 双层脱敏。设备主列表与 Inventory 等辅助
查询保持独立，活动 Task 摘要失败不得改变 Device 主数据成功语义。
