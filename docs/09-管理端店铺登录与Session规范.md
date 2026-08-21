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

本阶段没有已验证的服务器只读平台接口，因此写入状态为 `captured`、`validated_at = NULL`。`captured` 只表示真实身份已识别且认证状态已采集，不等价于服务器 HTTP 已验证。首次版本仍要求 `expected_version = 0` 并生成版本 `1`，后续更新继续使用乐观并发版本。

## 5. 本地 Profile

每次未完成接入使用：

```text
persist:management-login-<login_attempt_id>
```

Electron 按 Chromium persistent session 规范把实际 Profile 保存在应用 `userData` 私有目录，而不是 Git 仓库、系统 Chrome Profile 或 `frontend/public`。成功后，本地 `management-login-profiles.json` 只保存 `shop_id → partition` 映射；完整 Profile 永不上传服务器。

## 6. 安全 IPC

Renderer 只能使用类型化的：

- `management-login:open`
- `management-login:get-status`
- `management-login:complete`
- `management-login:close`

参数经过白名单校验。不存在任意 JavaScript、通用 IPC、Shell 或 Profile 文件读取能力。`contextIsolation = true`、`nodeIntegration = false`、`sandbox = true` 保持不变。

## 7. 明确未实现

- 自动验证码和验证码 Provider；
- 账号密码自动填充或自动登录；
- Session 定时检测与自动恢复；
- Worker Browser Profile、Worker 自动登录或 Credential 下发；
- 影刀读取 Session；
- Backend 平台 HTTP Connector 与服务器有效性验证。
