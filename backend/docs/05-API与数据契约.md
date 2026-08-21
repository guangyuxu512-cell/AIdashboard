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

当前正式 Provider 为 `yingdao`。影刀 Inventory 只包含版本、登录状态、安全账号元数据、
当前 userId、未回收应用的 ID/名称/package version/entrypoint 与发现时间；禁止密码、
Token、Cookie 和完整认证响应。应用数组作为外部 Provider 最新快照存入专用 JSONB，
不是通用业务 JSON，也不是中控台 Skill 注册表。
