# 平台认证与 Session 架构

## 1. 统一认证链路

```text
Shop Onboarding（阶段 3C-1：当前 Electron 管理电脑）
↓
PlatformAuthAdapter
├─ 人工验证码 / 扫码 / 滑块 / App 确认
├─ DiscoveredShopIdentity → 创建 Shop + 绑定 Credential
└─ SessionSnapshot → 版本检查 → 加密保存 ShopSession
```

阶段 3C-1 使用 Electron persistent session 完成首个抖店真实采集闭环。未来 Session Refresh 才进入 Backend Task → 授权 Worker → Worker Browser Profile，不得把管理电脑伪装成 Worker Device。

## 2. PlatformAuthAdapter

每个平台实现独立 Adapter，上层只依赖统一能力：开始登录、检测状态、提交验证响应、读取真实店铺身份、生成 Session Snapshot。Adapter 不负责 UI、数据库或任务调度。

Platform Registry/Catalog 必须把“平台注册”与 `shopOnboarding`、`authentication`、`sessionCapture`、`dataFetch`、`rpa` 等能力分别标记。注册不等于所有能力已完成。

## 3. VerificationChallenge 与 Provider

Challenge 类型固定为 `sms_code`、`email_code`、`qr_scan`、`app_confirm`、`manual`。平台 Adapter 判断何时产生何种 Challenge；Frontend 后续只实现一个 `VerificationChallengeDialog`，按类型渲染。

`VerificationProvider` 根据配置解析 Challenge，后续可实现 Manual、Email、SmsHardware。Provider 不写入 Shop 表，API Key 等渠道配置必须进入独立安全配置域。本阶段没有任何 Provider 实现。

## 4. Browser Profile 与 SessionCapture

管理端首次接入按登录尝试使用独立 Management Login Profile，成功后在本机建立 Profile 与真实 `shop_id` 的映射。未来 Worker 侧仍执行 `Device × Shop = 独立 Browser Profile`；两者不是同一种 Profile，禁止共享默认 Chrome Profile。

服务器不保存完整 Browser Profile，只集中保存加密 Credential、加密 Session Snapshot 与业务数据。SessionCapture 成功后必须携带旧版本，通过乐观并发控制写入新版本。

## 5. SessionRefresh 与数据抓取

Session 维护是状态驱动：有效则复用；无效或需刷新时，由授权 Worker 使用 Credential、Challenge 和独立 Profile 重新认证，成功后生成更高版本 Session。

可使用服务器 Session 请求的平台数据，未来优先走 `Backend → Platform Connector → ShopSession → Platform`；必须依赖浏览器环境的数据走 `Backend Task → Worker → Browser/RPA`。阶段 3A 两条执行链均不实现。

## 6. 敏感数据边界

Frontend 只读脱敏账号及 Session 元数据。Worker 未来也不能枚举凭证，只能在合法 Task 和设备授权范围内临时获取所需 Secret。密码、验证码、Cookie、Token、Session payload 不得进入普通 API、日志、错误或审计内容。

账号密码是 Session 恢复的基础能力：Browser Profile 或 Cookie 失效后，授权 Device 只能在合法 Task 范围内临时取得目标 Shop 的 Credential，完成重新登录与验证，再写入更高版本 Session。Frontend Onboarding 在 Shop 尚未由平台探测创建前只收集短生命周期表单值，不伪造 `shop_id` 或提前调用 Credential Create。
