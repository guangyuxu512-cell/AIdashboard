# 平台认证与 Session 架构

## 1. 统一认证链路

```text
Shop Onboarding / Session Refresh
↓
Backend Task（后续）
↓
授权 Worker + 独立 Browser Profile
↓
PlatformAuthAdapter
├─ VerificationChallenge → VerificationProvider / 统一 Challenge UI
├─ DiscoveredShopIdentity → 创建 Shop + 绑定 Credential
└─ SessionSnapshot → 版本检查 → 加密保存 ShopSession
```

阶段 3A 只定义 Contract，不启动浏览器、不接验证码渠道、不采集 Cookie。

## 2. PlatformAuthAdapter

每个平台实现独立 Adapter，上层只依赖统一能力：开始登录、检测状态、提交验证响应、读取真实店铺身份、生成 Session Snapshot。Adapter 不负责 UI、数据库或任务调度。

Platform Registry/Catalog 必须把“平台注册”与 `shopOnboarding`、`authentication`、`sessionCapture`、`dataFetch`、`rpa` 等能力分别标记。注册不等于所有能力已完成。

## 3. VerificationChallenge 与 Provider

Challenge 类型固定为 `sms_code`、`email_code`、`qr_scan`、`app_confirm`、`manual`。平台 Adapter 判断何时产生何种 Challenge；Frontend 后续只实现一个 `VerificationChallengeDialog`，按类型渲染。

`VerificationProvider` 根据配置解析 Challenge，后续可实现 Manual、Email、SmsHardware。Provider 不写入 Shop 表，API Key 等渠道配置必须进入独立安全配置域。本阶段没有任何 Provider 实现。

## 4. Browser Profile 与 SessionCapture

设备侧执行 `Device × Shop = 独立 Browser Profile`，禁止多店铺共享默认 Chrome Profile。概念路径为 `profiles/<platform_code>/<shop_id>/`，实际路径由未来 Worker Runtime 定义。

服务器不保存完整 Browser Profile，只集中保存加密 Credential、加密 Session Snapshot 与业务数据。SessionCapture 成功后必须携带旧版本，通过乐观并发控制写入新版本。

## 5. SessionRefresh 与数据抓取

Session 维护是状态驱动：有效则复用；无效或需刷新时，由授权 Worker 使用 Credential、Challenge 和独立 Profile 重新认证，成功后生成更高版本 Session。

可使用服务器 Session 请求的平台数据，未来优先走 `Backend → Platform Connector → ShopSession → Platform`；必须依赖浏览器环境的数据走 `Backend Task → Worker → Browser/RPA`。阶段 3A 两条执行链均不实现。

## 6. 敏感数据边界

Frontend 只读脱敏账号及 Session 元数据。Worker 未来也不能枚举凭证，只能在合法 Task 和设备授权范围内临时获取所需 Secret。密码、验证码、Cookie、Token、Session payload 不得进入普通 API、日志、错误或审计内容。
