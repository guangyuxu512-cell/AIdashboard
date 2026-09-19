# Access Management V1

> **历史 V1：** 本文描述的 `access_admin`、成员级模块授权和成员级 `SELF/TEAM/ALL`
> 已由 `20260919_0037_super_account_team_authorization_v1` 替代。现行人员、Team、资源
> 授权、移出/调组/归档与删除契约以
> [23-超级账号与团队授权V1.md](23-超级账号与团队授权V1.md) 为准；本文只保留 0025 的
> Migration 与旧客户端字段背景。

## 目标与边界

Access Management V1 在既有 Human Auth、User、Team、TeamMembership、ActorContext 和
Data Scope 基础上，提供 PC 管理端的“用户与权限”能力：创建人员、管理其登录凭据、维护 Team
关系，以及为每条 Membership 配置可访问的系统模块。

本期只管理企业内部人员身份，不改变 Worker Device Token、Worker API、Task/Shop/Schedule 的
既有历史认证模型；不实现通用 RBAC、ACL、角色继承、审计中心、部门树、批量导入或 Hard Delete。
Team 和 Membership 的启停仍是生命周期边界。

## 最小角色与数据范围

可管理角色固定为：

- `member`：普通人员。
- `access_admin`：可以访问人员、Team、Membership 和模块授权管理接口。

角色与 Data Scope 完全分离。Data Scope 继续沿用 `self / team / all`，只影响已采用
ActorContext 的业务数据查询；`access_admin` 不自动拥有 `all`，也不自动获得任何业务模块。
本期不把其它历史 `role_code` 解释或迁移为管理员。

每个管理操作都以当前选中的启用 Membership 为准。人员、Membership 或 Team 已停用时不能构成
有效管理上下文。系统必须始终保留至少一条“启用人员 + 启用 Team + 启用 Membership”的
`access_admin` 关系；停用最后一名管理员、停用其最后的有效 Team/Membership，或将其降级为
`member` 都必须被拒绝。

初始化不猜测管理员。运维只可显式执行：

```text
python -m app.cli.human_auth grant-access-administrator <membership_id>
```

命令只会授予一条现存且有效的 Membership；不会创建人员、不会写入密码、不会硬编码任何 UUID。

## 模块访问

模块访问是 Membership 级关系表，而不是第二份前端模块清单：

```text
team_memberships 1 ── * membership_module_accesses
```

`membership_module_accesses` 的复合主键是 `(membership_id, module_code)`。有效代码来自当前
Frontend Module Registry 的正式用户模块：`shop`、`asset`、`ai-workbench`、`device`、`task`、
`schedule`、`settings`。development-only `foundation` 与未知代码均不允许保存。

前端从同一个 Module Registry 生成授权复选项、Sidebar 过滤和路由模块识别；不会另建一份
module-code 常量。后端使用 `ModuleCode` 枚举校验输入，读取到未知持久化值时 fail closed。

本期服务端模块 Guard 已施加到唯一现有的 Human ActorContext 业务 API——资料库的所有人员路由，
它要求 `asset`。AI、店铺、设备、任务、计划等现有历史 API 尚未迁移至 Human Management Plane，
因此本期只做前端菜单/路由过滤，不宣称它们已由后端 Module Guard 保护；不得为了表面完整性改变
其既有 Worker 或匿名 Contract。

## 人员与凭据

新人员创建在单一事务中写入 User、初始 Membership 和模块访问。登录账号按 Human Auth 既有规则
规范化并唯一；密码使用既有 Argon2 `PasswordService` 哈希。密码仅在 Create 或 Reset 请求体内存在，
不进入任何 Read DTO、日志、Query Cache、URL、CLI 参数或数据库明文字段。

重置密码和停用人员均撤销该人员全部 Human Session。重置后仍沿用既有服务端 Cookie 会话模型；
人员重新启用不恢复旧会话。人员管理不提供删除接口。

## API 与错误语义

`GET /api/v1/access-management/me/module-access` 返回当前 Membership 的模块代码与是否为权限管理员。
其余 `/api/v1/access-management/members`、`/members/{user_id}`、`/memberships/{membership_id}`
和 `/teams` 管理路由均要求 `access_admin`。完整字段和路径以 Pydantic Schema 与
`05-API与数据契约.md` 为准。

无人员会话返回 `HUMAN_AUTHENTICATION_REQUIRED`；非管理员返回
`ACCESS_ADMINISTRATION_FORBIDDEN`；缺少业务模块访问返回 `MODULE_ACCESS_DENIED`；破坏唯一有效
管理员边界返回 `LAST_ACCESS_ADMINISTRATOR_REQUIRED`。无效角色、模块代码或重复模块代码在请求校验
阶段拒绝；重复登录账号、重复 Team Membership、停用 Team 等继续返回既有领域错误。

## Migration

Migration `20260902_0025_access_management_v1` 在已分配的 Slot 中创建
`membership_module_accesses`，并为升级时已经存在的 Membership 回填当前全部正式模块访问，避免
历史已登录人员因本次上线立即失去菜单。它不会自动授予 `access_admin`，不会改动 Data Scope 或
任何 Worker 身份。Downgrade 只删除该关系表；真实 `head → previous → head` 闭环只能在已登记的
Feature DB `control_center_feat_access` 中执行。
