# Logging & Audit V1

## 当前交付与边界

本期分为两个独立边界：请求运行日志与 Access Management 审计记录。它们不共用一张表，也不引入
ELK、Loki、OpenTelemetry、Kafka、Redis、事件总线或通用 Policy/Audit Framework。

当前已交付的是非持久化请求日志。Access Management 审计持久化尚未开始：当前 Green `dev` 的
Alembic Head 是 `20260903_0026`，工程登记表显示 `control_center_feat_access` 已回收，且没有向
`feat/logging-audit-v1` 分配 Feature DB 或登记 Migration Slot。得到这两项分配前，不得创建 Audit
Model、Migration、审计 API 或前端入口，也不得写入 `control_center_dev` 或
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

## 待持久化的 Access Management 审计范围

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

`update_member` 的现有 Schema 只允许 `enabled`；`update_membership` 是当前 Role、Data Scope、
Membership 状态与 Module Access 的唯一更新入口；`update_team` 是 Team 启停的现有入口。上述映射不
扩大为 Team 树、通用 RBAC、资源 ACL 或 CLI bootstrap 的第二套审计语义。

拿到登记的 Feature DB 与 Migration Slot 后，审计实现必须使用一个最小审计表，并在同一个
`AccessManagementService` Session 中、现有管理写入 `commit` 前追加审计记录，确保业务变更与审计
记录原子提交。详情只保存上述稳定 ID、实际变更字段名和已解析的 actor 上下文；不得保存完整对象
快照、密码、密码哈希、Cookie、Token、验证码或 Session payload。

届时才可实现 `access_admin` 专属的审计分页读取（按时间、actor、action 过滤）及 System Settings
中的审计入口。普通成员必须由 Backend 拒绝读取，前端隐藏或路由拒绝不能替代该权限边界。
