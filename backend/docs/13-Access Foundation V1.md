# Access Foundation V1

## 1. 定位

Access Foundation V1 为单组织、多 Team、多 User 建立统一管理平面身份上下文：

```text
Human Authentication
        ↓
HumanPrincipal(user_id)
        ↓
TeamMembership(role_code, data_scope)
        ↓
ActorContext
        ↓
DataScopePolicy
```

本阶段只建立基础设施，不把现有业务表半迁移为多租户，也不建设 Team 管理 UI、动态 RBAC、ACL、
Organization 或 Department。

## 2. Team 与 Membership

`Team` 是数据归属团队，字段为 `team_id / name / enabled / created_at / updated_at`。

`TeamMembership` 是 User 与 Team 的稳定关系，字段为：

- `membership_id`
- `team_id`
- `user_id`
- `role_code`
- `data_scope`
- `enabled`
- `created_at / updated_at`

同一 `(team_id, user_id)` 只能存在一条关系。Team 与 Membership 通过 enabled 停用；本阶段不提供
Hard Delete 流程。

Role 与 Data Scope 必须分开：Role 为未来动作权限保留，Scope 决定可见数据范围。当前唯一默认
Role Code 是可扩展字符串 `member`，没有 roles/permissions 表。

## 3. ActorContext 与 Active Team

ActorContext 是 FastAPI 请求级对象，只包含：

```text
user_id
user_display_name
team_id
membership_id
role_code
data_scope
```

它不携带 User/Team/Membership ORM 对象、Request 或 WorkerPrincipal。

Active Team 解析规则：

1. 一个 Active Membership 且未传 `X-Team-ID`：自动选择唯一 Team。
2. 多个 Active Membership：必须传 `X-Team-ID`。
3. 指定 Team：Backend 验证 User 的 Membership、Membership.enabled 和 Team.enabled。
4. 无 Active Membership、非成员、停用关系或多 Team 未选择：返回明确错误。

前端传入的 Team ID 只表示选择意图，不是授权事实。

## 4. Data Scope

V1 只允许：

- `SELF` (`self`)：`team_id = actor.team_id AND created_by_user_id = actor.user_id`
- `TEAM` (`team`)：`team_id = actor.team_id`
- `ALL` (`all`)：不追加 Ownership Filter

DataScopePolicy 接收 SQLAlchemy Statement、Team 列、创建者列和 ActorContext，不知道 Asset、Task、
Shop 或 AI Job 等具体领域。未知/非枚举 Scope 一律抛错，禁止默认 ALL。

ALL 只影响读取过滤，不代表 Create 可以没有 Team。未来任何 Team Scoped Entity 创建时仍必须写入
明确 Active Team。单实体 Detail 的默认实现也应使用 `entity_id + scope predicate` 同一个 SQL，
避免泄漏记录是否存在。

## 5. Human Auth 现状

审计确认当前 User 只有 `user_id / display_name / enabled`，不存在稳定唯一登录标识、密码 Hash 或
Human Session。现有 `modules/authentication` 是店铺平台登录接入，不是 Human Auth；Worker Bearer
Token 只属于执行平面。

因此本阶段没有自创新 username/email，也没有建立不可登录的伪 Session 表。`get_human_principal`
是正式、安全的认证接入缝，当前默认返回 `HUMAN_AUTHENTICATION_REQUIRED`，且不接受任意
`X-User-ID`。一旦产品确定 Human Login Identifier Contract，可在该边界实现最小 Human Session，
无需改变 ActorContext 或业务 Service。

## 6. API

- `GET /api/v1/access/me`：当前 ActorContext；多 Team 时使用 `X-Team-ID`。
- `GET /api/v1/access/me/teams`：当前 Human User 的全部 Membership 摘要，包含 Team 与 Membership
  启用状态。

My Teams 是选择 Team 的 Bootstrap API，因此它只要求有效 HumanPrincipal，不要求预先解析 Active
Team。两个 API 在 Human Auth 接入前都会安全返回 401。

## 7. 默认团队迁移

Migration `20260831_0022_access_foundation_v1` 创建一个“默认团队”。升级时已经存在的每个 User
获得且只获得一条启用 Membership：

```text
role_code = member
data_scope = team
```

空 User 表正常升级；Migration 不依赖固定 User UUID。没有任何用户被自动授予 ALL。

## 8. Worker 边界

Worker 继续只通过 Device Token 与 `X-Device-ID` 认证。未来 Human User 在创建 Task 前完成 Scope
检查；Task 成功创建后 Worker 只消费 Task，不重新解析 Membership 或 Human Data Scope。

## 9. Phase B

本阶段没有给任何现有业务实体增加 Ownership。后续顺序：

1. B1 Asset Scope
2. B2 Task / Schedule Scope
3. B3 Shop Scope
4. AI Image Ownership Integration

未来 Team Scoped Entity 统一使用：

```text
team_id             数据归属 Team
created_by_user_id  创建者
```

`owner_user_id` 不能同时承担权限边界。AI Image Job 未来写入相同两个字段，Reference Asset 必须通过
Actor Scope 校验；生成成功后调用正式 `AssetService.create(...)`，生成 Asset 继承相同 Ownership。
Asset 与 AI Job 仍是不同领域。
