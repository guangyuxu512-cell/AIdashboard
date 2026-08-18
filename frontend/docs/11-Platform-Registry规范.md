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
backendSupported
createSupported
```

- `enabled`：是否在前端平台导航等展示入口出现。
- `backendSupported`：当前 Backend 是否存在正式平台 Contract。
- `createSupported`：当前 Create Shop 是否允许提交该平台。

禁止在 Registry 提前加入 Auth Adapter、Cookie Strategy、验证码 Provider、RPA Script 等未来执行配置。

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

因此淘宝、视频号在平台栏正常展示，在 Create Shop Select 中显示“待接入”并禁用。Frontend 不得提交后再依赖 Backend 报错，也不得扩展 DTO、Query、Mapper 或数据库枚举。

平台栏在 Backend 没有正式筛选参数时，只筛选当前已加载 ViewModel，并必须在代码中明确为 client-side filter。

## 6. 新增平台流程

未来增加平台（例如快手）时：

1. 在 `entities/platform/assets` 增加正式图标。
2. 在 `PLATFORM_REGISTRY` 增加一条定义，并按真实能力设置支持字段。
3. 若 Backend Contract 正式扩展，再单独更新对应业务 Contract 与 Mapper。

平台栏、平台 Select、Table 和 Drawer 不应再逐个修改 Options 或显示组件。

## 7. 账号与连接边界

“账号与连接”是 Shop 基础主档之外的独立后续业务动作。它未来负责平台登录账号、凭证、授权、Verification Challenge、Cookie / Session 状态及 Session 维护；本阶段只提供“未配置”入口，不实现 Credential、Cookie、验证码或登录成功状态。

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

可能的 Challenge 类型仅作为方向记录，不在本阶段建立接口：

```text
SMS_CODE / EMAIL_CODE / QR_SCAN / APP_CONFIRM / MANUAL
```

未来 Provider 可包括 Manual Verification、Email Provider、SMS Hardware Provider。本阶段不创建空实现、伪接口或 Python 类。

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
