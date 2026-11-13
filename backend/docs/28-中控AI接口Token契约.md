# 中控 AI 接口 Token

中控人员管理员可以通过独立页面 `/token-manager/` 创建和管理提供给 AI 的 Token。页面使用既有人员登录 Cookie，不创建新的管理密码。AI 以 `Authorization: Bearer <Token>` 请求原有 `/api/v1/` 管理接口；API Base 为部署入口，接口文档为同一入口的 `/openapi.json`。Token 不是 Worker 凭据，也不能调用 Worker、应用间或手机上传专用接口。

## 管理接口

以下接口只接受已登录的超级账号，不接受 AI Token 来签发其他 Token。每次签发、修改和撤销写入 Token 专用审计；完整值只在创建响应中返回一次，响应禁用缓存。数据库仅保存摘要，不保存 Token 明文。专用审计与既有日志分开，以便回退旧应用时旧日志查询仍可用。

| 方法与地址 | 用途 |
| --- | --- |
| `GET /api/v1/api-tokens/permissions` | 返回当前可配置的管理操作目录 |
| `GET /api/v1/api-tokens` | 列出 Token 配置和状态，不返回摘要或完整值 |
| `POST /api/v1/api-tokens` | 创建 Token，响应 `value` 仅显示一次 |
| `PUT /api/v1/api-tokens/{token_id}` | 完整更新名称、权限、团队、启用状态和有效期 |
| `PATCH /api/v1/api-tokens/{token_id}/enabled` | 停用或重新启用，不改其他配置 |
| `GET /api/v1/api-tokens/{token_id}/events` | 查看该 Token 的管理记录 |
| `DELETE /api/v1/api-tokens/{token_id}` | 撤销，重复撤销幂等；不可恢复 |

创建或更新使用 `{ "name": "AI 名称", "permissions": ["GET /api/v1/tasks"], "team_ids": null, "enabled": true, "expires_at": null }`。权限 ID 是 HTTP 方法与 OpenAPI 路径模板。权限选择保存为当时的明确操作集合，后续新增接口不会自动授权；缺失、未知或未经选择的接口一律拒绝。有效期使用带时区的 ISO 8601；创建时必须在未来。Token 被停用、撤销、过期或发放者不再是启用的超级账号时，下一次请求立即拒绝。

`team_ids: null` 表示沿用发放者的全部团队权限；指定团队时，请求必须用 `X-Team-ID` 指定允许的团队。团队限定 Token 仅可选择权限目录中标记 `team_scoped` 的操作，身份按普通团队权限解析并继续遵守已有模块与数据隔离，不自动扩大到其他团队；原本只允许超级账号的全局操作不能以团队限定 Token 使用。具体写操作仍须满足现有团队和业务规则。请勿将 Token 放进 URL、日志、仓库或公开聊天。

## 迁移与回滚

新增 `20261113_0051`，新增 Token 和 Token 审计表。数据库备份须连同既有业务数据妥善保护；从旧备份恢复可能令已经撤销的 Token 重新有效，恢复后须核实并撤销受影响凭据。共享和生产回滚保留表与审计，通过回退应用关闭入口；降级只允许空的已登记 Feature 数据库。
