# RPA 接入规范

RPA 是 Skill 的一种设备侧实现方式，不承担任务调度或服务器业务。

正式链路：

```text
Backend Task → Worker → RPAExecutor → YingdaoAdapter → 影刀
```

RPAExecutor 只负责确认 Provider、校验本地 App 映射、执行超时、统一 Result 转换
和 Runtime 收口。影刀发现与触发细节只允许存在于 YingdaoAdapter。

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

Discovery 最小返回 `provider_available`、可选 `account_display` 与 applications；每个
Application 只包含 `app_id`、`app_name`。

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

因此本阶段未把该旧格式接入生产 Adapter，也未猜测影刀 CLI/API/App ID。生产使用
UnavailableYingdaoAdapter 明确返回 `RPA_PROVIDER_UNAVAILABLE`；待提供真实测试应用
ID、触发入口和结构化结果格式后，再实现具体 FileTrigger 或 CLI Adapter。

禁止：

- Backend 直接操作影刀或执行电脑文件。
- RPA 自己轮询中控台或访问 PostgreSQL。
- RPA 硬编码账号密码、Cookie 或 Token。
- Backend Task 直接绑定影刀应用名称。
- 错误后无状态退出或无限等待人工输入。

浏览器 Profile 与 Credential/Session 下发不属于本阶段。
