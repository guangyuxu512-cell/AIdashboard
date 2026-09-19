# Human Auth V1

> **权限解析更新：** 人员登录与服务端 Session 契约仍有效；但从
> `20260919_0037_super_account_team_authorization_v1` 起，超级账号不需要默认团队，
> 普通成员至多一条有效 Membership。本文关于 Bootstrap 加入默认团队、多 Team 选择和
> Membership Role/Data Scope 的内容已被
> [23-超级账号与团队授权V1.md](23-超级账号与团队授权V1.md) 覆盖。

## 1. 定位

Human Auth V1 为思余AI中控台提供企业内部人员登录。正式链路是：

```text
人员登录
↓
验证规范化登录账号与 Argon2 密码 Hash
↓
创建服务端人员会话（Human Session）
↓
识别当前人员（HumanPrincipal）
↓
选择当前团队（X-Team-ID）
↓
解析团队成员关系（TeamMembership）
↓
生成请求身份上下文（ActorContext）
↓
应用数据范围策略（DataScopePolicy）
```

V1 不建设互联网 IAM，不包含用户管理页面、Team CRUD、Membership CRUD、动态权限编辑、短信、
OAuth、MFA 或密码找回。

## 2. 为什么不使用 JWT

本系统当前是由 Backend 统一提供管理 API 的企业内部应用，不需要让多个独立服务离线验证身份。
服务端 Opaque Session 可以直接撤销、可在 User 停用后立即拒绝，也不需要 Refresh Token、Rotation、
Blacklist 与权限 Claims 同步。因此 V1 使用“账号密码 + Argon2 + 服务端 Session”，不引入 JWT。

Session Token 只表达“这是一条可能有效的登录会话”，不携带 Team、Role 或 Data Scope。每次请求都
以数据库中的最新 User 和 Membership 事实为准。

## 3. Human 与 Worker 身份边界

两套身份完全分离：

| 身份 | 用途 | 凭据 |
|---|---|---|
| Human User | 管理平面页面与 API | 账号密码登录后的 HttpOnly Cookie |
| Worker Device | 执行平面心跳、Claim、Capability 与回传 | Bearer Device Token + `X-Device-ID` |

Human Session 不复用 Worker Credential 表；Worker Token 不进入 Human Session 表；
`HumanPrincipal` 不进入 Worker 认证链，`WorkerPrincipal` 也不进入 `ActorContext`。

## 4. User 登录字段

`users` 增加两个可空字段：

- `login_name`：企业内部登录账号，最多 100 个字符。
- `password_hash`：成熟密码 Hash，不保存明文或可逆密文。

`login_name` 统一执行 `trim + lower`，Service 不允许空白字符；数据库通过 Check Constraint 固定
首尾与大小写规范，并通过 Unique Constraint 保证唯一。`display_name` 继续只用于展示，不能作为
唯一登录凭据。

历史 User 的两个字段均允许为 `NULL`，Migration 不生成默认账号或密码。Credential 不完整的历史
User 不能登录，管理员必须通过安全 CLI 显式设置。

## 5. 密码 Hash 与策略

密码由 `PasswordService` 统一处理，底层采用 `pwdlib` 推荐参数的 Argon2。API、CLI 和 Service
调用方不得直接操作底层 Hash。

V1 密码长度为 10 至 256 个字符，不强制大写、小写、数字、符号的机械组合。不同 Hash 使用独立
Salt；密码、`password_hash` 均不会进入 API 响应或业务日志。未知账号仍执行一次 Dummy Hash
校验，再返回与错误密码相同的 `HUMAN_LOGIN_FAILED`，降低账号枚举与明显时间差风险。

## 6. 服务端人员会话

`human_sessions` 字段：

- `session_id`
- `user_id`
- `token_hash`
- `expires_at`
- `revoked_at`
- `created_at`

登录时生成 48 字节 Crypto Secure 随机值并使用 URL-safe 编码。Raw Token 只写入 `Set-Cookie`；
数据库仅保存 64 字符 SHA-256 Hash，用于等值索引查询。这里的 SHA-256 用于高熵随机 Token，不能
替代密码的 Argon2。

默认 Session TTL 是 604,800 秒（7 天），可通过
`BACKEND_HUMAN_SESSION_TTL_SECONDS` 在 5 分钟到 30 天范围内明确配置。

解析顺序为：Session 存在、未撤销、未过期、User 仍存在、User 已启用。任一条件失败均 Fail
Closed。重置登录凭据会撤销该 User 的全部旧 Session；退出登录撤销当前 Session，重复退出保持幂等。

## 7. Cookie、CORS 与 CSRF 姿态

默认 Cookie：

```text
Name      siyu_human_session
HttpOnly  true
Path      /api/v1
SameSite  lax
Secure    development=false / production=true
```

开发环境由 Vite 将 `/api` 代理到本机 Backend，浏览器看到的是同源请求，因此 HTTP 下显式使用
`Secure=false`。生产环境 Settings 校验强制 `Secure=true`；推荐 Frontend 与 API 通过同站 HTTPS
入口提供服务。

Electron 开发模式同样加载 `http://127.0.0.1:5173`，因此复用上述 Vite Proxy。打包后的 `file://`
页面不是正式的 Cookie 部署 Origin；生产 Electron 必须加载与 API 同站的 HTTPS Frontend 入口，
不能通过放开 `Origin=null` 或把 Raw Session Token 交给 Renderer 绕过这一边界。

默认 `BACKEND_CORS_ALLOWED_ORIGINS=[]`，表示同源模式不启用跨域 Credential。确有分离 Origin 时，
必须填写显式 JSON Origin 列表；通配 `*`、重复 Origin、`SameSite=None + Secure=false` 和生产环境
`Secure=false` 会在启动配置校验时失败。CORS 只允许明确方法与 Header，并启用 Credentials。

V1 的 CSRF 边界由同站 HTTPS、`SameSite=lax`、严格显式 CORS 和不接受任意 Credential Origin
共同构成。当前拓扑不需要额外 CSRF Token；若未来改为必须跨站发送 Cookie，应先重新审计并增加
正式 CSRF Contract，而不是静默改为 `SameSite=None`。

## 8. API Contract

- `POST /api/v1/auth/login`：输入 `login_name/password`，成功设置 Cookie，仅返回
  `user_id/display_name`。
- `POST /api/v1/auth/logout`：撤销当前 Session、删除 Cookie；重复调用可成功。
- `GET /api/v1/auth/me`：只解析 HumanPrincipal，不依赖 Team 选择。
- `GET /api/v1/access/me/teams`：只依赖 HumanPrincipal，返回可用于选择的 Membership 摘要。
- `GET /api/v1/access/me`：HumanPrincipal + `X-Team-ID` 解析完整 ActorContext。

主要错误：

- `HUMAN_LOGIN_FAILED`：账号不存在、密码错误或历史 User 没有 Credential 的统一对外语义。
- `HUMAN_AUTHENTICATION_REQUIRED`：没有 Cookie。
- `HUMAN_SESSION_INVALID`：未知、过期或已撤销会话。
- `HUMAN_USER_DISABLED`：User 已停用。
- `TEAM_CONTEXT_REQUIRED`：多 Team 用户尚未选择 Team。

## 9. HumanPrincipal 与多 Team

`HumanPrincipal` 只包含 `user_id/display_name`。它是 `get_human_principal` 的唯一正式输出，不包含
Team、Role、Data Scope 或 ORM 对象。

单一 Active Membership 用户登录后自动选择唯一 Team。多个 Active Membership 用户先调用
`/auth/me` 和 `/access/me/teams`，在 PC 端选择 Team 后再通过统一 HTTP Client 发送 `X-Team-ID`。
Backend 始终重新校验 Membership 与 Team 状态，前端保存的 Team ID 只是选择意图，不是授权事实。

PC 端按 User ID 在 `localStorage` 保存最后选择的 Team ID，但不保存 Raw Session Token，也不保存
`isLoggedIn=true` 作为身份事实。刷新页面必须调用 `/auth/me` 恢复服务端 Session；服务端 401 才会
清理本地认证状态并跳转登录页。主动退出或已登录 Session 失效时，同时清除该 User 的 Team 偏好；
下次多 Team 登录需要重新选择。

## 10. 首次账号初始化与凭据重置

安全 CLI：

```powershell
cd backend
.venv\Scripts\python.exe -m app.cli.human_auth bootstrap `
  --display-name "系统管理员" `
  --login-name "admin"

.venv\Scripts\python.exe -m app.cli.human_auth set-credentials <USER_UUID> `
  --login-name "zhangsan"
```

密码只通过 `getpass` 交互输入并二次确认，不支持命令行 Password 参数，不输出密码或 Hash。

`bootstrap` 仅允许在 `users` 数量为 0 时创建第一个启用 User，并加入 Migration 建立的“默认团队”，
Role 为 `member`、Data Scope 为 `team`。只要已有任意 User 就拒绝 Bootstrap。系统不存在
`admin/admin` 或任何默认密码。

`set-credentials` 为指定历史 User 设置或重置账号密码，成功后撤销该 User 的全部旧 Session。

## 11. PC Login 与当前用户

PC Router 将 `/login` 标记为公开认证布局。业务路由 Guard 会先调用 Store 的 Session Restore；未
认证时带安全的站内 Redirect 跳转 Login，多 Team 未选择时停留在选择步骤。登录页和业务区继续
复用现有 Light/Dark Design Token，不改变 Sidebar 宽度、Topbar 高度或页面布局。

Topbar 在 Theme 控件旁显示当前用户菜单，其中包括当前用户、当前 Team、多 Team 切换与退出登录。
统一 Axios Client 使用 `withCredentials=true`，集中附加 `X-Team-ID`。只有 Human Session 的明确
401/403 Code 会触发退出；Worker 认证或普通业务错误不会被误判为 Human Session 过期。

## 12. 当前业务接入边界

Human Auth V1 打通认证、HumanPrincipal、ActorContext 与 Access API；Asset、Device、Task 与 Schedule
按各自既有模块规则使用 ActorContext 与 DataScopePolicy。Shop、Credential、Shop Session 与 Shop
Onboarding 管理路由使用 Human Session、ActorContext 与 `shop` 模块访问，但尚未建立 Shop Ownership
Scope；不得把该模块防护误解为数据隔离。Automation Application Config 与 Notification Channel 分别使用
`device` 与 `settings` 模块访问。Worker Token 链保持独立，不能套用 Human Guard。
Frontend Guard 只改善交互，不是安全边界。

未来 Access Management 位于“系统设置 → 用户与权限”，但 V1 不实现新增成员、Team 管理、
Membership 管理或权限编辑页面。

## 13. Migration 与日志安全

Migration `20260831_0023_human_auth_v1` 从 `20260831_0022` 增加 User Credential 字段与
`human_sessions`。它允许旧 User 保持 NULL Credential，支持空库、旧数据升级以及
upgrade/downgrade/upgrade。共享开发数据库不能因单个功能分支测试而升级，验证必须使用隔离测试
数据库或临时 Schema。

API 响应、Frontend Store、Runtime Event、Task Result 与日志禁止出现 Raw Password、Raw Session
Token、`password_hash` 或 `token_hash`。生产排障只能记录安全错误码、Request ID 与脱敏摘要。
