# Mobile Auth V1

## 状态与范围

Mobile Auth V1 状态：`Completed / Candidate for Integration`。

本轮只接入已有 Human Auth / Access Management，完成登录、Session 恢复、当前 Team、
Module Access、受保护路由与退出。不增加 JWT、注册、找回密码、MFA、OAuth、
生物识别或新的 Backend Auth Contract。

## 真实 Backend Contract

| 方法 | Path                                         | Request / Response                             |
| ---- | -------------------------------------------- | ---------------------------------------------- |
| POST | `/api/v1/auth/login`                         | `login_name/password` → `user_id/display_name` |
| POST | `/api/v1/auth/logout`                        | 撤销 Session 并清 Cookie → 204                 |
| GET  | `/api/v1/auth/me`                            | 有效 Session → `user_id/display_name`          |
| GET  | `/api/v1/access/me/teams`                    | `MyTeamMembershipRead[]`                       |
| GET  | `/api/v1/access-management/me/module-access` | `module_codes/is_access_administrator`         |

Session 默认 Cookie 名为 `siyu_human_session`、Path 为 `/api/v1`、HttpOnly、
SameSite=Lax，TTL 默认 7 天，Secure 按 Backend 环境配置。Mobile Axios Client 使用
`withCredentials: true`，不读取 Cookie，不创建 Authorization/JWT Header。

## 客户端责任

```text
Router / App Bootstrap
↓
Human Auth Pinia Store
↓
Human Auth Entity DataSource
↓
shared/api 唯一 Axios Client
↓
Backend Human Auth / Access API
```

- Auth Store 只保存当前运行期 User、Team、Module Access 和恢复状态。
- 密码只存在当次登录表单，提交后清空；Session Token 从不进入 JavaScript Storage。
- localStorage 唯一 Auth 相关数据是 `control-center.active-team.<userId>` Team 偏好。
- Team 变更或 Auth 清理时清空 TanStack Query 缓存。
- `X-Team-ID` 只由共享 Axios Interceptor 注入，Page/Feature/Entity 不重复传递。

## Session 恢复与 Team

受保护 Route 或 `/login` 首次进入时只执行一次并发安全的初始化：

1. `/auth/me` 确认服务端 Session。
2. `/access/me/teams` 只保留 Team 和 Membership 均启用的候选。
3. 单 Team 直接选中；多 Team 使用登录页最小选择界面。
4. 选定 Team 后读取 `/access-management/me/module-access`。

恢复失败必须进入匿名或可重试终态，不允许无限 Loading。

## Module Access 与 Router

- `/devices`、`/devices/:deviceId` 要求 `device`。
- `/tasks`、`/tasks/:taskId` 要求 `task`。
- `/schedules` 要求 `schedule`，`/shops` 要求 `shop`。
- `/me` 只要求有效 Human Session，用于当前账号和 Logout。
- 无权业务入口不显示；直接 URL 导航到 `/permission-denied`。
- 未登录目标以安全内部 `redirect` 保留，登录后返回。

Frontend Module Access 只是体验边界，Backend 仍必须对每个领域 API 执行授权与
Data Scope。Mobile 不复制 Role 或 Data Scope 算法。

## 错误和退出

- `HUMAN_LOGIN_FAILED`：显示“登录账号或密码错误”。
- `HUMAN_USER_DISABLED`：显示“当前账号不可用”并清理已恢复身份。
- `HUMAN_AUTHENTICATION_REQUIRED` / `HUMAN_SESSION_INVALID`：清理 User/Team/Access 并返回登录。
- 其他错误：只显示安全摘要“暂时无法登录”，不透出 Axios/HTTP 实现。
- Logout 必须先调用 `/auth/logout`；成功后再清理本地运行期状态并返回 `/login`。

## UI 与验收

登录页仅使用已有 Mobile Token、Vant Form/Field/Button/Radio 与 Safe Area，只包含登录
账号、密码、登录按钮、安全错误和真实必需的多 Team 选择。不得增加假状态栏、
欢迎说明、插画、第二套 Theme 或页面私有颜色。

核心 E2E 必须覆盖：登录成功/失败、深链拦截与回跳、刷新恢复、Session 失效、Logout、
单/多 Team、`X-Team-ID`、device/task 有权和无权、360/375/390/430 Light/Dark、
44px Touch Target、Console/Page Error 与横向溢出。

## 已知 Backend Contract Gap

Human Auth / Access Management 本身已有正式 Contract，但当前 Device 与 Task 旧 Router 未注入
`require_module_access('device' | 'task')`，也未按 Actor Context 实施服务端 Data Scope。
本 Feature 不修改 Backend；该 Gap 必须由 Backend Feature 单独收口，在此之前不得将 Mobile
入口隐藏宣称为安全授权。
