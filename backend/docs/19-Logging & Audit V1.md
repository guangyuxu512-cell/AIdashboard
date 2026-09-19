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

## Access Management 审计范围

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
