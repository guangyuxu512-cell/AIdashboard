# Logging & Audit V1

> **0037 覆盖说明：** `20260919_0037_super_account_team_authorization_v1` 后，新的
> 人员/Team 管理动作由超级账号执行，且全局管理审计可没有 `team_id`。本文件下文关于
> `access_admin` 和成员级 Membership 授权的描述仅保留旧审计事实；现行权限边界见
> [23-超级账号与团队授权V1.md](23-超级账号与团队授权V1.md)。

## 当前交付与边界

本期分为两个独立边界：请求运行日志与 Access Management 审计记录。它们不共用一张表，也不引入
ELK、Loki、OpenTelemetry、Kafka、Redis、事件总线或通用 Policy/Audit Framework。

请求日志已交付；Access Management 审计使用独立 Feature DB
`control_center_feat_audit` 开发验证。Migration Slot 为
`20260904_0028_logging_audit_v1`，Revision 为 `20260904_0028`，唯一
`down_revision` 为 `20260903_0027`。不得操作 `control_center_dev` 或
`control_center_integration`。

## 请求运行日志

`RequestLoggingMiddleware` 为每个实际进入 Backend 的请求输出一行 JSON。固定字段为：

- `request_id`：沿用请求头 `X-Request-ID`；缺失时生成 UUID。
- `method`、`path`、`status_code`。
- `latency`：完整请求耗时，单位为毫秒。

可从已解析的真实请求上下文获得时，日志额外包含：

- `user_id`：Human Session 解析成功后的人员 ID。
- `team_id`：`ActorContext` 解析成功后的 Team ID。
- `module`：路由已有的第一个 FastAPI tag。
- `error_code`：统一错误处理器已有的领域错误码，或未处理异常的
  `INTERNAL_ERROR`。

成功与失败响应都会返回同一个 `X-Request-ID`。日志只取上述字段和路由 tag；不得读取或输出
request body、query、Cookie、Authorization、密码、Token、验证码或 Session payload。请求日志仅用于
运行排障，不是业务审计事实。

### Session refresh 的有限拒绝日志

仅既有 refresh API 捕获 `SHOP_SESSION_PAYLOAD_INVALID` 时，使用模块 logger
`app.modules.sessions.api` 输出一条 WARNING JSON；记录后仍抛出原异常，HTTP/code/message 不变。
这是业务失败诊断，不是新的审计表、通用日志框架或请求访问日志替代品。

固定 `event=shop_session_refresh_payload_rejected`、`error_code=SHOP_SESSION_PAYLOAD_INVALID`。
其余仅允许 `request_id`、`refresh_stage`、`validation_step`、`schema_issues`、`schema_issues_truncated`；
阶段/子步骤和最多三个字段类别/错误类型沿[Session 契约](10-账号凭证与Session规范.md)白名单投影。
不输出任意 details、异常文本/栈、原 loc/msg/input/ctx、请求 body/query/header/URL、身份值或 Cookie 名称/值。

新 domain 日志的 request_id 只接受已有的 36 字符带连字符 UUID 形状（大小写均可），否则固定
`unavailable`；缺省请求头仍复用全局生成的 UUID。不会反射任意 `X-Request-ID` 原值，也不更改原全局
请求 ID、响应头或 access 日志契约。合法 UUID 在响应/domain/access 中一致；`unavailable` 不能冒充已关联请求。

使用现有 server stdout/stderr 的受保护收集路径，不增开关或日志端点；正式部署后由 Main 核销该 WARNING
确实进入日志出口。ASGI 内存请求和真实 `logging.StreamHandler` 的合成验证不等于生产失败已定位。

## Access Management 审计范围

候选池0046增量复用audit_logs：product_selection.block_candidate／product_selection.restore_candidate，
target_type=selection_candidate，目标同Team Candidate UUID；只保存blocked_before/blocked_after、
当前授权Actor及候选保存Team。同状态重复不审计，变更与审计同事务；查询/失败不造成功审计。
basic尝试由原Run记录，不另建通用日志或保存平台原响应/凭据。

审计只记录成功提交的管理写入；读取和失败写入不创建审计记录，失败由请求运行日志覆盖。下列 action
值直接对应当前 `AccessManagementService` 的真实成功方法，避免另造未存在的业务动作：

| 当前服务方法 | 待记录 action | 最小目标信息 |
| --- | --- | --- |
| `create_member` | `access_management.create_member` | 新 `user_id`、初始 `membership_id` |
| `update_member` | `access_management.update_member` | `user_id`、`enabled` 变更 |
| `reset_member_password` | `access_management.reset_member_password` | `user_id`；绝不记录密码或哈希 |
| `create_membership` | `access_management.create_membership` | `user_id`、新 `membership_id`、`team_id` |
| `update_membership` | `access_management.update_membership` | `membership_id`、实际变更字段名 |
| `create_team` | `access_management.create_team` | 新 `team_id` |
| `update_team` | `access_management.update_team` | `team_id`、实际变更字段名（含 `enabled`） |
| `move_member_to_team` | `access_management.move_member_team` | `user_id`、旧关系 ID、新 Team/关系 ID |
| `move_member_to_team(team_id=null)` | `access_management.remove_member_from_team` | `user_id`、被停用关系 ID |
| `archive_team` / `delete_team` | `access_management.archive_team` / `delete_team` | `team_id`、受影响成员数（归档时） |
| `update_team_authorization` | `access_management.update_team_authorization` | `team_id`、模块/设备/店铺数量及失效会话计数 |

`update_member` 的现有 Schema 只允许 `enabled`；`update_membership` 是当前 Role、Data Scope、
Membership 状态与 Module Access 的唯一更新入口；`update_team` 是 Team 启停的现有入口。上述映射不
扩大为 Team 树、通用 RBAC、资源 ACL 或 CLI bootstrap 的第二套审计语义。

`audit_logs` 是本期唯一的审计表。它只保存 `request_id`、操作人 `actor_user_id`、当前
`team_id`、`action`、目标类型及 ID、创建时间，以及可空的最小 `details`。详情只保存稳定 ID、
实际变更摘要（例如 Data Scope 的前后值）或 Module Access 的增删 code；不得保存完整对象快照、
密码、密码哈希、Cookie、Token、验证码或 Session payload。

审计记录在同一个 `AccessManagementService` Session 内、业务 `commit` 前追加，确保业务变更与
审计记录原子提交。密码重置只记录该操作成功，详情为空。

管理员查询接口为 `GET /api/v1/access-management/audit-logs`，只允许 Human Auth 的
`access_admin`。它复用通用分页并支持 `created_from`、`created_to`、`actor_user_id` 与 `action`
筛选；普通成员由 Backend 返回 403。PC 端在 System Settings 提供 `/settings/audit-logs`“操作日志”
页面，同样以 `requiresAccessAdministrator` 隐藏入口并拒绝路由访问，但前端不替代 Backend 权限边界。
