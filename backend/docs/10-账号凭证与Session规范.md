# 账号凭证与 Session 规范

## 1. 领域关系

```text
PlatformCredential ──< ShopCredentialBinding >── Shop ── ShopSession
```

`PlatformCredential` 表达平台登录账号，保存平台、统一登录标识、加密 Secret、首选验证码渠道和启用状态。账号不能直接写入 `shops`：同一平台账号未来可能发现并管理多家店铺，凭证生命周期也独立于店铺主档。

`ShopCredentialBinding` 负责关联。一个 Credential 可绑定多家同平台 Shop；当前一个 Shop 最多有一个启用 Binding，不提前引入多角色凭证策略。

## 2. Credential 安全

- `login_identifier` 统一承载手机号、邮箱、用户名或账号 ID。
- `secret_encrypted` 使用 `cryptography.fernet.Fernet` 与服务器环境密钥 `BACKEND_ENCRYPTION_KEY` 加密。
- 数据库、日志、错误、审计和 Read API 均不得出现明文密码。
- 更新请求中账号或密码空字符串表示不修改；只有非空新密码才替换密文。
- Read API 只返回脱敏标识、`configured`、`enabled`、验证码渠道和更新时间。由于 Create 时 Secret 必填，Frontend 可由 `configured` 派生“密码已配置”，API 不增加任何 password read 字段。

密钥不进入 Git。无有效密钥时 Credential/Session 敏感写入必须显式失败。

## 3. ShopSession

`ShopSession` 每店铺一条当前快照，持有 `version`、必要状态、来源设备、采集/验证/可选过期时间，以及 `payload_encrypted`。Payload 可以承载 Cookie 和必要认证快照，但不是任意业务 JSON 容器。

状态包含：`not_configured`、`captured`、`valid`、`invalid`、`refresh_required`。`captured` 表示真实登录身份已经识别且 payload 已加密保存，但尚未通过服务器只读平台接口验证；不得把它展示成 `valid`。未配置时数据库无需伪造空 Session，由 Metadata Service 返回版本 `0`。

管理端首次登录不是 Worker，使用 `source_device_id = NULL`。未来 Worker 重采集才写入真实 Device ID，禁止为管理电脑伪造 Device。

Session payload 与密码共用成熟的加密基础设施，但在领域上互相独立。普通 API 只返回元数据，绝不返回 Cookie、payload 或密文。

## 4. 并发版本

首次写入必须携带 `expected_version=0`，生成版本 `1`。后续更新以数据库条件更新 `WHERE shop_id = ... AND version = expected_version` 并原子递增。版本不匹配返回冲突，旧设备不能覆盖新 Session。

## 5. Worker 下发边界

本阶段不提供 Secret 或 Session payload 的 HTTP Route。未来只能在合法 Task、目标 Shop、目标 Device 和授权校验全部成立后临时下发本次认证所需内容；禁止 `GET /all-credentials`，禁止设备批量下载。

Browser Profile 永远保留在设备侧，并按 `Device × Shop` 隔离；服务器集中管理 Credential、Session 与业务数据，不上传完整 Chrome Profile。

## 6. 管理端原子接入

阶段 3C-1 的完成命令由 Electron Main 在 Adapter 已确认身份并采集 payload 后调用。Backend 在单个数据库事务内创建 Shop、PlatformCredential、ShopCredentialBinding 与 ShopSession；失败全部回滚。Shop 使用 `(platform, platform_shop_id)` 唯一约束避免同一平台店铺重复接入。

## 7. 审计与后续实现

Credential 变更、Session 版本变更及授权读取未来必须接入审计，但审计只记录主体、对象、动作和结果，不记录敏感值。阶段 3A 只建立 Domain、API 元数据和认证 Protocol，不实现 Worker、浏览器、Cookie 采集、验证码 Provider 或平台 Connector。
