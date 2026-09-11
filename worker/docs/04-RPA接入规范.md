# RPA 接入规范

RPA 是 Skill 的一种设备侧实现方式，不承担任务调度或服务器业务。

正式链路：

```text
Backend Task → Worker → RPAExecutor → YingdaoAdapter → 影刀
```

RPAExecutor 只负责确认 Provider、校验 Task App ID、执行超时、统一 Result 转换
和 Runtime 收口。影刀应用执行细节只允许存在于 YingdaoAdapter；只读环境发现由
独立的 `YingdaoDiscoveryService` 承担，不能借 Discovery 启动应用。

## 影刀本地输入桥接

新影刀 Application 需要普通参数、账号或图片时，统一读取 Worker GUI 配置的：

```text
params.json
account.json
images 目录
```

不得由每个 Application 自行定义另一套 Worker 路径。RPAExecutor 在取得当前 Task 的
`input.params`、确认 Provider 与 App 可用、并取得 Provider 执行槽后，先调用 Local Input
Bridge：完整覆盖两个 JSON 并确认图片目录；成功后才调用 `YingdaoAdapter.execute()`。
Preparation 与 ShadowBot Run 位于同一个 Provider 串行边界内，不会被两个影刀 Task 交叉覆盖。

`params.json` 的根对象就是业务参数本身，不增加 context/runtime/resources Envelope；无参数为
`{}`。`account.json` 只使用认证 Claim 下发的正式有序 `accounts`，并仅在落盘边界映射为：

```json
{
  "店铺列表": [
    {
      "店铺ID": "...",
      "店铺名称": "...",
      "平台编码": "douyin",
      "登录账号": "...",
      "登录密码": "...",
      "首选验证方式": null
    }
  ]
}
```

无 Payload 固定写 `{"店铺列表":[]}`，不写英文重复字段。`params.json` 与 `account.json` 均
UTF-8、中文不转义、原子替换并对每个 Task 完整覆盖。完整账号数据不得进入日志、Runtime Event
或 Task Result。现有
`shadowbot:Run?...` Application Params 保持兼容，不因增加固定文件而删除。

`params.json` 的键严格来自 Backend 已保存 Schema 的 `name`，允许且必须原样保留 Unicode 业务键
（例如 `商品列表`）；Worker 不翻译、拼音化、解析 JSON 形状的 text 值或重命名这些键。`text` 默认值
即使形如 JSON 也保持 JSON string，避免把配置参数误变为另一个类型。

一个多店铺 Task 只准备一次 `account.json` 并启动一次 ShadowBot Application。Worker 不循环
店铺、不判断切号或验证码；Application 自行决定串行、切号、单店失败后是否继续，并通过现有
最终结果 Contract 决定 Task 终态。

当前尚无 Server → Worker 图片传输 Contract，V1 只保证图片目录存在且可写，不猜测图片来源、
文件名或集合切换。详细跨 Runtime 规则见 `03-Skill执行规范.md`。

必须支持：

- 外部启动与输入。
- 明确成功或失败。
- 超时退出。
- 结构化结果和稳定错误码。
- 日志与 Runtime 隔离。

统一运行目录：

```text
runtime/<task_id>/
├── input.json
├── status.json
├── output.json
├── stdout.log
├── stderr.log
└── artifacts/
```

## Yingdao Adapter Contract

Discovery 正式返回 provider、available、status/reason、provider_version、logged_in、
account_display、account_type、enterprise_account、user_id、applications 与
discovered_at。每个 Application 只包含当前会话 API 已验证提供的安全元数据：
`app_id`、`app_name`、`version_id`、`updated_at`、`app_type`、`group_id`，不包含密码、
Token、Cookie、流程内容或完整认证响应。

## ShadowBot 6.3.6 当前会话 Discovery

`yingdao.discover` 是可重试的 Provider Inventory 发现能力，不属于影刀 App 执行。
正式链路固定为：

```text
运行中 ShadowBot 主进程
→ 读取真实 EXE 路径与文件版本
→ 按进程监听端口动态定位 loopback endpoint
→ GET /api/v1/account/current
→ GET /api/v1/apps
→ GET /api/v1/apps/{appId}/detail（执行前可访问性复核）
```

正式 Runtime 不读取 `user.db3`、`username.ini`、`developmentsync_apps_v2` 或
`apps/<uuid>/package.json` 来判断当前账号和云端应用。多账号缓存不会再参与当前会话判断。
`shadowbot.shell-cli` 也不在正式 Discovery 链。`%LOCALAPPDATA%/ShadowBot/users/.../task_logs`
仅保留为实际运行日志来源。

端口不能写死为 42500；Worker 只探测当前 ShadowBot 进程实际监听的 loopback 端口。
没有进程时通过配置覆盖、Windows 安装信息和标准候选目录定位 6.3.6 并启动，等待接口
就绪有明确超时。若已运行其他版本，Worker 不结束该进程，也不启动第二实例。

ShadowBot 6.3.6 的真实接口样本存在 `Code/Data` 与 `code/data` 两种 Envelope 大小写。
Session、Application List 和 Application Detail 必须先经过同一个轻量 Normalizer，再读取
内部字段；缺少 Code 或 Data 属于协议错误，不得默认成功或静默转换为空对象。后台 Provider
刷新使用的进程与端口查询 CLI 必须通过 Worker 的 Windows 无窗口子进程入口执行并保留
stdout/stderr 与 Return Code，Heartbeat 本身只进行 HTTP 通信。

Provider 状态固定为 `not_installed / version_unsupported / starting / need_login /
interface_unreachable / ready`。这些都是可上报 Inventory 状态，不会让 Worker Heartbeat、
Poll 或其它 Executor 退出。

成功结果：

```json
{"status":"success","result":{}}
```

失败结果：

```json
{
  "status":"failed",
  "error_code":"RPA_EXECUTION_FAILED",
  "error_message":"..."
}
```

当前 Worker Provider 与 Execution 都固定为影刀 6.3.6：

| 版本 | Discovery | Execution |
|---|---|---|
| 6.3.6 | Current Session API | VERIFIED |
| 其他版本 | UNSUPPORTED | 禁止执行 |

当前不存在版本优先级和回退链。后续只有在运行中版本、接口与当前账号能够可靠关联后，
才允许通过新的正式设计恢复多版本支持。

安装 Root 可以直接指向 6.3.6 目录，也可以指向包含 `shadowbot-6.3.6` 的上级目录。
版本目录的真实入口为 `ShadowBot.Shell.exe`，同时兼容旧布局中的 `ShadowBot.exe`。
即使 Root 中同时存在其他版本，Runtime Locator 也只选择文件版本为 6.3.6 的入口，不选择根目录
中的更高版本，也不回退到更低版本。其他版本可以保留在磁盘，无需由 Worker 删除。

真实启动只允许以 subprocess argument list、`shell=False` 的等价方式直接启动 Locator
选中的入口（根 `ShadowBot.exe` 或版本目录 `ShadowBot.Shell.exe`），第二个参数为按 URI 规则编码的
`shadowbot:Run?robot-uuid=<appUuid>&key=value`。这里禁止的是 cmd 的 `start ""`
包装形式，不是禁止直接启动 ShadowBot.exe。不得使用 StandaloneLauncher、UI 坐标点击、
未知 URI 变体或直接运行应用内部脚本。

同一 Worker 第一版同时最多执行一个影刀任务。启动前必须确认 App UUID 仍在当前账号
云端应用列表，并通过 detail 接口复核可访问。Task 的成功
至少需要关联启动后产生的新 tasklog、匹配目标 App 的真实 started 记录和真实 exited
记录。启动进程退出或 tasklog 文件存在都不等于成功；失败规则只能来自已验证样本。
没有安全停止入口时，超时不得杀掉整个 ShadowBot.exe。

RuntimeYingdaoAdapter 通过 Worker Runtime Event Bus 上报状态和 tasklog 增量日志，
Provider 不直接请求 Backend。通用稳定 Skill 为 `yingdao.app.run`，输入固定为
`app_id + params`；Backend 在创建 Task 前校验目标设备最新 Provider Inventory 与参数
Schema，Worker 执行前再次校验当前账号可访问该 App。

禁止：

- Backend 直接操作影刀或执行电脑文件。
- RPA 自己轮询中控台或访问 PostgreSQL。
- RPA 硬编码账号密码、Cookie 或 Token。
- Backend Task 直接绑定影刀应用名称。
- 错误后无状态退出或无限等待人工输入。

浏览器 Profile 与 Credential/Session 下发不属于本阶段。
