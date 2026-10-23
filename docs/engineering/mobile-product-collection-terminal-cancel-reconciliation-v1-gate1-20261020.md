# 手机商品采集取消终态对账 Gate 1 补充

## 范围与真实失败证据

- 基线／原候选：`51cc138af6c265269c2266fe2b43a4a7b6378ea0`；分支保持
  `feat/mobile-product-collection-integration-v1`。本补充只修中央 Backend，不修改 Android、Electron、
  Frontend、Schema、Migration、配置或执行开关。
- ca97 的一台真实设备证据显示：网关 Job 已在 attempt 1/1 后进入 `failed`，没有 upload/persist 回执；
  随后中控已经记录正式取消意图，但既有 PATCH cancel 收到网关 409“状态已变化”，中央 Request、Item、
  Dispatch 因而仍为 running。该证据证明的是终态契约缺口，不证明手机 Hook 原始事件数为 0。
- 手机完整包生成问题由用户直接协调手机项目，本候选不修改或派发 Android 工作，也不新增对接接口。

## 最小修复

- HTTP 适配器只识别网关当前版本的精确终态冲突格式，并且只接受 `failed`、`canceled`。正常取消与已取消
  重放返回 typed `GatewayCancelResult`；未知文案、`completed`、其它 409、HTTP／网络错误仍按原安全错误
  分类抛出，不从任意文本猜测状态，也不泄露响应正文。
- 中央取消消费者在网关 I/O 后重新锁定原 Dispatch、Item、Request，复核 Team、当前 Dispatch 和
  `gateway_job_id`。网关已经 failed 时写入 `execution_failed/failed` 及脱敏错误，同时结束活动 Attempt；
  正式取消仍写 canceled。取消发起人和时间原样保留。
- 迟到结果、不同 Team、已被新 Dispatch 取代或本地已经终态的记录不会被覆盖。临时网关错误不会进入
  对账方法，因此不会伪造终态；下一轮仍可沿原消费者重试取消。

## 验证边界

- HTTP 合成：正常取消、精确 failed/canceled 冲突、未知／completed 冲突及 503；敏感内容不进入异常。
- Feature PostgreSQL：精确 Head `20261020_0049`，只运行不会暴露可领取任务的两项对账测试，验证四层状态、
  取消审计、幂等重放及较新 Dispatch fence。Feature 库仍有 ca97 的运行消费者，因此没有重跑会创建
  pending delivery 的整文件测试，避免后台消费者抢领夹具。
- 首次定向回归发现该库仍保留 Gate 2 真实失败行；全局消费者先命中该行，并通过本修复路径将其从 running
  收口为 failed。该动作使用合成的网关 failed 结果，虽然与 ca97 已保存的真实网关终态证据一致，仍不冒充
  新的真实网关请求。原 JSON／截图证据保持不变。
- 未执行手机新任务、真实网关请求、平台请求、生产数据库、第二 Electron、push、PR、CI、dev/main 合并或部署。

| 检查 | 结果 |
| --- | --- |
| Product Collection 六个定向文件 | 48 passed；网关 cancel 正常、failed/canceled 冲突、未知冲突、503 及原 API/执行器/cleaner/contract/model 回归通过 |
| Feature PostgreSQL 精确对账 | 2 passed、13 deselected；0049 Head，四层失败收口、取消审计、重复结果和较新 Dispatch fence 通过 |
| Backend 默认离线 | 1133 collected/passed、474 integration deselected；仅既有 Starlette/httpx deprecation warning |
| `pnpm verify` / `pnpm verify --strict` | Node 24.19 + pnpm 11.25 均 exit 0，0 known/new/stale；默认 Shell Node 20 首次运行因缺少 `node:sqlite` 失败，已按仓库既有 Node 24 运行门槛重跑，不改依赖或配置 |
| Python / diff | `compileall app tests`、`git diff --check` 均 exit 0 |

最终 Candidate、测试计数和工作树状态以正式 Handoff 为准。
