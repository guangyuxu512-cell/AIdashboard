# 管理端店铺登录与 Session 规范

## 1. 四个概念

```text
Credential
  账号与密码，服务器使用 BACKEND_ENCRYPTION_KEY 加密保存

ShopSession
  平台 Cookie 与当前 Origin 必要存储快照，作为服务器后续 HTTP 认证来源
  payload 对 Backend 领域是不透明密文

Management Login Profile
  当前 Electron 管理电脑上的持久化登录环境
  只服务首次人工登录、人工重新验证和后续 Session 恢复

Worker Browser Profile
  未来由每台 Worker 按绑定店铺独立创建，本阶段不存在
```

Profile 本地、Session 服务器。Backend HTTP 使用 ShopSession，不读取、同步或依赖 Management Login Profile。另一台电脑即使没有原始 Profile，也能通过 Backend 读取 Shop 主档和 Session 元数据；未来平台 HTTP Connector 只消费服务器侧 ShopSession。

## 2. 首次接入流程

```text
选择平台
→ 在 Renderer 内存中填写账号与密码
→ Electron 为 login_attempt_id 打开独立 persistent session
→ 用户人工完成验证码、扫码、滑块或 App 确认
→ PlatformAuthAdapter 自动探测真实平台身份
→ Electron Main 采集不透明 Session payload
→ 用户确认店铺
→ Backend 单事务创建 Shop、Credential、Binding、ShopSession
→ Electron 在本地记录 shop_id 到 persistent partition 的映射
```

首次登录不选择 Worker，也不创建虚假 Device。管理端采集写入 `ShopSession.source_device_id = NULL`。用户关闭登录窗口或接入失败时，Backend 尚未收到完成命令，不产生列表可见的半成品 Shop。

## 3. 抖店 V1 适配依据

阶段 3C-1 只开放抖店。登录入口和账号识别接口来自既有真实项目的登录采集实现；Adapter 只有在账号接口同时返回非空 `account_id`、`account_name`，且持久化 Session 中存在已验证登录 Cookie 时，才报告成功。`account_id` 映射为 `platform_shop_id`，`account_name` 映射为 `display_name`。

拼多多、淘宝和视频号没有同等级真实证据，保持未接入，UI 不允许进入假登录流程。

## 4. Session payload 与状态

抖店 V1 payload 使用平台私有 `management-login.session.v1` 序列化结构，包含：

- 平台与已识别店铺身份；
- `jinritemai.com` 域下的 Cookie；
- 当前登录 Origin 的 localStorage / sessionStorage 快照；
- 采集时间。

Payload 不经过 Renderer，不提供读取 API，也不记录日志。Electron Main 只通过固定 Adapter 脚本采集，Renderer 不能传入 JavaScript。Backend Base64 解码后立即使用 Fernet 加密落库。

首次采集写入 `captured`、`validated_at = NULL`。`captured` 只表示真实身份已识别且认证状态已采集，不等价于服务器 HTTP 已验证。Backend 随后通过抖店 `shop_info_v2` 只读接口验证远端 `shop_id` 与本地 `platform_shop_id`；成功才写 `valid`。首次版本要求 `expected_version = 0` 并生成版本 `1`，后续更新继续使用乐观并发版本。

## 5. 本地 Profile

每次未完成接入使用：

```text
persist:management-login-<login_attempt_id>
```

Electron 按 Chromium persistent session 规范把实际 Profile 保存在应用 `userData` 私有目录，而不是 Git 仓库、系统 Chrome Profile 或 `frontend/public`。成功后，本地 `management-login-profiles.json` 只保存 `shop_id → partition` 映射；完整 Profile 永不上传服务器。映射只在文件不存在时初始化为空；损坏、结构无效或无法读取时必须保留原文件并报错，写入以临时文件替换且同一 Main 内串行化多店读改写。

首次接入或 Session 恢复的 Backend 已成功后，如本机映射写入失败，接入/恢复仍视为成功并清理该次尝试，响应通过 `profileMappingWarning` 明示本机恢复环境未保存；Renderer 不得将其显示为可重发的业务失败。用户下次恢复时按无本机 Profile 的人工登录路径继续。

## 6. 安全 IPC

Renderer 只能使用类型化的：

- `management-login:open`
- `management-login:get-status`
- `management-login:complete`
- `management-login:refresh`
- `management-login:close`

参数经过白名单校验。不存在任意 JavaScript、通用 IPC、Shell 或 Profile 文件读取能力。`contextIsolation = true`、`nodeIntegration = false`、`sandbox = true` 保持不变。

## 7. 健康检查与恢复

Session 健康判断由 Backend `ShopSessionHealthService` 统一完成。只有平台明确返回 HTTP 401/403 或 Connector 已有证据的认证失效响应才写 `invalid`；Timeout、DNS、网络错误、平台 5xx、响应结构异常只表示本次无法验证，不改变 Session 状态。`validated_at` 的新鲜窗口由 Backend 配置统一控制，不建立全店铺定时 Cron。

Cookie 不保证永不过期，Cookie `expires` 只用于预警，平台只读验证才是权威。真实响应包含 `Set-Cookie` 时按 name/domain/path 合并并保留 HttpOnly、Secure、SameSite、expires；无 `Set-Cookie` 时不伪造续期、不增加版本。

恢复优先级：

1. 当前 Session 仍有效则继续使用；
2. 当前管理电脑存在 Management Profile 时重新采集；
3. Profile 已掉线或本机无 Profile 时由用户人工登录；
4. Credential 自动登录留待后续；
5. Worker Profile 恢复留待后续。

同一店铺恢复前获取 Backend 可过期 Refresh Lease，提交使用开始时取得的 `expected_version`。完成、取消、窗口提前关闭和超时均释放 Lease；异常退出由 Lease 到期恢复。Profile 始终是本机资产，不跨电脑同步；不同电脑可用各自 Profile 更新同一服务器 ShopSession。

## 8. 明确未实现

- 自动验证码和验证码 Provider；
- 账号密码自动填充或自动登录；
- 全店铺后台定时巡检；
- Credential 自动填充、自动验证码；
- Worker Browser Profile、Worker 自动登录或 Credential 下发；
- 影刀读取 Session；
- Worker Session 恢复。
