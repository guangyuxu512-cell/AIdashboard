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
- `/shops`：GET list、GET detail、POST create、PATCH update。
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

错误统一返回 `code`、`message`、`request_id`、可选 `details`。V1 业务错误码包含 `USER_NOT_FOUND`、`SHOP_NOT_FOUND`、`DEVICE_NOT_FOUND`、`INVALID_DEVICE_BINDING`；请求校验使用 `VALIDATION_ERROR`，数据库异常统一映射为 `DATABASE_OPERATION_FAILED`。

Pydantic Create、Update、Read Schema 是正式 API Contract。Frontend 的 GMV、Session/自动化状态、CPU/内存、Worker 版本、当前任务和展示文本不属于这些 Read Schema。

## Credential / Session Metadata Contract

阶段 3A 增加：

- `GET /api/v1/shops/{shop_id}/credential`：仅返回脱敏账号、配置/启用状态、验证码渠道和更新时间。
- `POST /api/v1/credentials`、`PATCH /api/v1/credentials/{credential_id}`、`POST /api/v1/credentials/{credential_id}/disable`：写入与停用凭证。
- `GET /api/v1/shops/{shop_id}/session`：仅返回 Session 状态、版本、来源设备和时间元数据。

Credential Read 不含密码、密文；Session Read 不含 Cookie、payload 或密文。密码只存在于 Create/Update 写请求，Update 的空字符串表示保留现有密码。Session payload 的写入目前只属于内部 Service Contract，不开放普通 Frontend Route。
