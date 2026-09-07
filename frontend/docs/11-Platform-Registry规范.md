# Platform Registry 规范

## 1. 定位

`frontend/src/entities/platform` 是前端平台展示元数据的唯一正式来源。Platform 是 Shop、Product、Order、Data Center、Task 等模块都会复用的实体概念，不属于 Shop 页面私有配置。

权威结构：

```text
entities/platform/
├── assets/            平台图标
├── model/registry.ts  平台定义与派生数据源
├── ui/                PlatformIcon / PlatformDisplay
└── index.ts
```

## 2. 最小 Registry 字段

每个平台只维护当前已验证需要的字段：

```text
code
label
icon
enabled
registered
capabilities
```

- `enabled`：是否在前端平台导航等展示入口出现。
- `registered`：平台是否已进入正式 Catalog；不代表任何具体业务能力可用。
- `capabilities`：按 `available | planned | unavailable` 分别声明 Legacy Shop Create、Credential Management、Shop Onboarding、Authentication、Session Capture、Data Fetch 和 RPA。

Registry 只声明能力状态，禁止放入 Auth Adapter、Cookie Strategy、验证码 Provider、RPA Script 等执行配置。

## 3. 唯一来源规则

以下界面必须从 Registry 或其派生函数读取：

- Shop Center Platform Bar。
- Create / Edit Shop 平台 Select。
- Shop Table 平台 Icon + Label。
- Shop Detail Drawer 平台 Icon + Label。
- 后续平台 Filter、Product、Order、Task 等平台展示。

禁止页面、Fixture、Mock DataSource、Real DataSource 各自维护 `platformOptions`、平台 Label 或图标路径。

## 4. Icon 规则

图标统一存放于 `entities/platform/assets`，通过 `PlatformIcon` / `PlatformDisplay` 解析。禁止 Emoji、页面内联 SVG、页面复制图片路径。Light / Dark 下使用同一正式资源并保持可辨识。

## 5. Frontend 与 Backend 支持边界

Frontend Registry 可先展示淘宝、视频号等规划平台，但不能据此推断 Backend 已支持。

当前 Shop Backend Contract 只支持：

```text
douyin
pdd
```

因此淘宝、视频号在平台栏正常展示，在 Legacy Create Shop Select 中显示“待接入”并禁用。正式 Onboarding Step 1 则按 `registered` 允许选择所有已注册平台，再通过独立 capability 在后续步骤显示“登录执行能力尚未接入”。Frontend 不得提交后再依赖 Backend 报错，也不得扩展 DTO、Query、Mapper 或数据库枚举。

平台栏在 Backend 没有正式筛选参数时，只筛选当前已加载 ViewModel，并必须在代码中明确为 client-side filter。

## 6. 新增平台流程

未来增加平台（例如快手）时：

1. 在 `entities/platform/assets` 增加正式图标。
2. 在 `PLATFORM_REGISTRY` 增加一条定义，并按真实能力逐项设置 capability。
3. 若 Backend Contract 正式扩展，再单独更新对应业务 Contract 与 Mapper。

平台栏、平台 Select、Table 和 Drawer 不应再逐个修改 Options 或显示组件。

## 7. 账号与连接边界

“账号与连接”是 Shop 基础主档之外的独立业务动作。正式能力管理登录账号、加密密码、Cookie / Session 元数据、验证方式和 Session 维护，其中账号和密码是必需能力，不得退化为只保存 Cookie 的临时入口。阶段 3A 已接入 Credential 配置和安全状态读取，并保留 Session 元数据入口；不实现 Cookie 采集、验证码执行或登录成功状态。

Frontend 只负责表单交互、状态展示和调用正式契约。密码加密、Credential 持久化、Cookie / Session 安全存储由 Backend 负责；认证执行与维护由后续 Worker/Backend Contract 负责。禁止在 Renderer、Query Cache 或 ViewModel 保存明文密码、完整 Cookie 或 Token。

未来认证链路遵循：

```text
Platform Auth Adapter
↓
Verification Challenge
↓
统一 Challenge UI
↓
Verification Provider
↓
ShopSession
```

平台 Adapter 决定当前需要哪类 Challenge；统一 UI 只展示 Challenge；Provider 决定验证码如何获得。不得为不同平台复制验证码 UI。

拼多多 V1 已接入管理端人工登录与 Session 采集；Electron 只采集适用于 `mms.pinduoduo.com` 的 Cookie，店铺身份由 Backend 平台接口验证，Renderer 不接收 Cookie、签名值或平台身份解析细节。商品、评价等业务数据拉取仍不属于当前接入能力。

正式 Challenge Contract 类型为：

```text
SMS_CODE / EMAIL_CODE / QR_SCAN / APP_CONFIRM / MANUAL
```

未来 Provider 可包括 Manual Verification、Email Provider、SMS Hardware Provider。阶段 3A 只建立 Backend Protocol，没有 Provider 实现。

## 8. Session 自动维护原则

Session 维护不得采用固定周期强制重登。正式实现应遵循状态驱动流程：

```text
检测 Session
├─ 有效 → 不处理
└─ 无效 → 恢复或重新认证
             ├─ 需要验证码 → Verification Challenge
             └─ 成功 → 更新 Session
```

该能力属于后续 Authentication / ShopSession 阶段，不进入当前 Frontend Registry 实现。
