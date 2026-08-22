# RPA 接入规范

RPA 是 Skill 的一种设备侧实现方式，不承担任务调度或服务器业务。

正式链路：

```text
Backend Task → Worker → RPAExecutor → YingdaoAdapter → 影刀
```

RPAExecutor 只负责确认 Provider、校验本地 App 映射、执行超时、统一 Result 转换
和 Runtime 收口。影刀应用执行细节只允许存在于 YingdaoAdapter；只读环境发现由
独立的 `YingdaoDiscoveryService` 承担，不能借 Discovery 启动应用。

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

Discovery 正式返回 provider、available、provider_version、logged_in、
account_display、account_type、enterprise_account、user_id、applications 与
discovered_at。每个 Application 只包含 `app_id`、`app_name`、`package_version`、
`entrypoint`，不包含密码、Token、Cookie 或完整认证响应。

## 已验证的只读 Discovery

`yingdao.discover` 是可重试的只读 Provider Inventory 发现能力，不属于影刀 App
执行。固定链路为：

```text
%LOCALAPPDATA%/ShadowBot/users
→ 显式配置 userId 时只读取该账号目录
→ 未配置时优先读取带 username.ini 与 user.db3 的当前 userId 目录
→ username.ini（明确的当前账号显示名标记）
→ 无 username.ini 时，仅接受唯一 user.db3 且 ownerName 唯一的账号目录
→ user.db3（SQLite read-only）
→ developmentsync_apps_v2 WHERE isRecycleBin = 0
→ apps/<appId>/xbot_robot/package.json
```

当前账号目录必须是纯数字 userId 并包含 `user.db3`。多账号电脑允许通过 Worker 的
`yingdao_user_id` 明确选择当前账号，选择后只读取该目录；该配置不包含密码或 Token。
未显式选择时，`username.ini` 存在则作为最高优先级
的明确当前账号标记；部分安装未生成该文件时，只允许在当前 Windows 用户下恰好存在一个
有效账号数据库，且活跃应用的 `ownerName` 唯一时确定账号。Worker 不会按目录时间、应用
数量或任意第一个目录猜测账号；存在多个无标记账号目录时明确失败。
数据库只读取 uuid、name、ownerName；package.json 只读取并校验 uuid、name、version、startup。
禁止写入影刀数据库。任一 package 损坏会让本次
Discovery 以 `YINGDAO_PACKAGE_INVALID` 失败并指出 App ID，不会令 Worker 进程退出，
也不会静默丢弃应用。

影刀 6.3.6 的登录状态不能被 6.3.9 CLI 复用，因此 Discovery 不启动
`shadowbot.shell-cli.exe`，不调用 `system health`、`auth current` 或 `console app`，也
不存在“6.3.9 CLI 优先 + Local DB fallback”。Local Discovery 是唯一正式来源。
本地数据未提供可验证的账号类型和企业标记时，`account_type` 与
`enterprise_account` 返回空值，不进行猜测。

当前已在 PersonalBasic 账号完成真实验证。个人账号的企业应用接口 5010 属于
not applicable，Discovery 不调用该接口，也不记录为系统错误。Enterprise 账号尚未
真实验证，不得宣称已支持。安装 Root、可选数据 Root 与可选 userId 进入 Worker Config；
发行包的影刀专用配置入口会列出本机候选 userId，且不要求重新输入 Device Token。数据 Root
默认仍使用启动 Worker 的当前 Windows 用户目录。代码不
硬编码本机路径。

`developmentsync_apps_v2` 是设备本地同步缓存，不是账号云端完整应用索引。同一账号
在不同电脑上可能得到不同数量。排查这类差异时使用独立的影刀只读诊断包，只采集
当前账号的安全元数据、应用索引安全字段、包存在性和候选表结构；不得上传原始数据库、
Token、Cookie、变量、流程或选择器。未来完整列表与本机可执行状态必须作为两个维度
建模，不能继续用本地缓存数量代表账号云端应用总数。

诊断包通过 `scripts/build-yingdao-diagnostic.ps1` 构建为
`dist/yingdao-readonly-diagnostic-win-x64.zip`。目标电脑完整解压后只需双击
`影刀只读诊断.cmd`，再回传生成的 `yingdao-diagnostic.json`。

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

Discovery 与 Execution 是两个独立能力。Inventory 必须分别表达
`discovery_available`、`execution_available`、`execution_version` 和不可执行原因；
Discovery 成功不能推出 Execution 可用。

账号与应用内容仍统一读取当前 Windows 用户下的 ShadowBot 本地缓存，不依赖 CLI。
但当前 Worker 发行版的 Provider 与 Execution 环境都固定为影刀 6.3.6；版本不匹配时
Discovery 也必须明确失败，避免“从一个版本发现、用另一个版本执行”的不确定行为：

| 版本 | Discovery | Execution |
|---|---|---|
| 6.3.6 | Local Discovery | VERIFIED |
| 其他版本 | UNSUPPORTED | 禁止执行 |

当前不存在版本优先级和回退链。安装 Root 缺少真实文件版本为 6.3.6 的入口时，返回
`YINGDAO_VERSION_UNSUPPORTED`，并说明当前 Worker 要求影刀 6.3.6。后续只有在运行中版本
与当前账号能够可靠关联后，才允许通过新的正式设计恢复多版本支持。

安装 Root 可以直接指向 6.3.6 目录，也可以指向包含 `shadowbot-6.3.6` 的上级目录。
版本目录的真实入口为 `ShadowBot.Shell.exe`，同时兼容旧布局中的 `ShadowBot.exe`。
即使 Root 中同时存在其他版本，Resolver 也只选择文件版本为 6.3.6 的入口，不选择根目录
中的更高版本，也不回退到更低版本。其他版本可以保留在磁盘，无需由 Worker 删除。

真实启动只允许以 subprocess argument list、`shell=False` 的等价方式直接启动 Resolver
选中的入口（根 `ShadowBot.exe` 或版本目录 `ShadowBot.Shell.exe`），第二个参数为按 URI 规则编码的
`shadowbot:Run?robot-uuid=<appUuid>&key=value`。这里禁止的是 cmd 的 `start ""`
包装形式，不是禁止直接启动 ShadowBot.exe。不得使用 StandaloneLauncher、UI 坐标点击、
未知 URI 变体或直接运行应用内部脚本。

同一 Worker 第一版同时最多执行一个影刀任务。启动前必须确认 App UUID 已在本机
Discovery Inventory 且 package 完整；云端存在但本机未同步时不得执行。Task 的成功
至少需要关联启动后产生的新 tasklog、匹配目标 App 的真实 started 记录和真实 exited
记录。启动进程退出或 tasklog 文件存在都不等于成功；失败规则只能来自已验证样本。
没有安全停止入口时，超时不得杀掉整个 ShadowBot.exe。

RuntimeYingdaoAdapter 通过 Worker Runtime Event Bus 上报状态和 tasklog 增量日志，
Provider 不直接请求 Backend。默认发行配置不映射任何真实 App；只有显式配置并经人工
确认无副作用的测试 App 才能进入真实 Run，业务 App 禁止作为工程验证对象。

禁止：

- Backend 直接操作影刀或执行电脑文件。
- RPA 自己轮询中控台或访问 PostgreSQL。
- RPA 硬编码账号密码、Cookie 或 Token。
- Backend Task 直接绑定影刀应用名称。
- 错误后无状态退出或无限等待人工输入。

浏览器 Profile 与 Credential/Session 下发不属于本阶段。
