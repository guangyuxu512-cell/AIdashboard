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
system health
→ 确认 console-restapi = ready
→ auth current
→ 使用响应中的 userId
→ %LOCALAPPDATA%/ShadowBot/users/<userId>/user.db3（SQLite read-only）
→ developmentsync_apps_v2 WHERE isRecycleBin = 0
→ apps/<appId>/xbot_robot/package.json
```

数据库只读取 uuid、name；package.json 只读取并校验 uuid、name、version、startup。
禁止扫描 users 目录猜测当前账号，禁止写入影刀数据库。任一 package 损坏会让本次
Discovery 以 `YINGDAO_PACKAGE_INVALID` 失败并指出 App ID，不会令 Worker 进程退出，
也不会静默丢弃应用。

当前已在 PersonalBasic 账号完成真实验证。个人账号的企业应用接口 5010 属于
not applicable，Discovery 不调用该接口，也不记录为系统错误。Enterprise 账号尚未
真实验证，不得宣称已支持。安装 Root 和可选数据 Root 进入 Worker Config，代码不
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

Adapter 可内部读取 `running/success/failed` 和 step/message，但本阶段只向 Backend
回传最终 Task 结果。Provider 不可用、应用未映射/不存在、触发失败、超时、非法
结果及影刀明确失败都必须结束 Task；只有 Worker Lease 失效才进入 LOST。

## 当前本机调查结果

本机已安装影刀，并发现旧调度源码使用 `Task_<tag>.json` / `Done_<tag>.txt` 文件
握手及本地 Tag 映射。但当前交换目录不存在，未发现实际消费 Task 文件并写 Done
文件的影刀流程；旧 Done 还是无结构文本，不能满足正式 FAILED/Result Contract。

因此旧格式仍未接入生产 Adapter。只读 Discovery 已正式接入，但真实 App 执行入口、
`app_id → run`、结构化运行结果仍未确认；生产执行继续由
UnavailableYingdaoAdapter 明确返回 `RPA_PROVIDER_UNAVAILABLE`。待执行契约真实验证
后，再实现具体执行 Adapter。

禁止：

- Backend 直接操作影刀或执行电脑文件。
- RPA 自己轮询中控台或访问 PostgreSQL。
- RPA 硬编码账号密码、Cookie 或 Token。
- Backend Task 直接绑定影刀应用名称。
- 错误后无状态退出或无限等待人工输入。

浏览器 Profile 与 Credential/Session 下发不属于本阶段。
