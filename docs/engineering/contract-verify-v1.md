# Verify 基础接入 V1

`verify` 汇总已登记的离线契约检查和已有五端验证，不调用平台、迁移共享数据库或启动应用。检查通过只代表本页所列范围通过，不代表全部 API、真实业务或生产已经验证。

## 入口与退出码

在仓库根目录使用已安装的项目 pnpm 和 Python 环境：

```powershell
pnpm verify
pnpm verify --strict
pnpm verify --full
pnpm verify --full --only=frontend,mobile,electron,worker
pnpm verify --report=.codex/verify-report.json
```

- 默认快速离线：检查器负向自测、权威 Python AST 与 TypeScript 编译器对照、正式 ASGI 错误响应及真实客户端的内存适配器探针。
- `--strict`：所有存量契约差异也失败，不使用例外。不是更换运行数据或修改业务源文件。
- `--full`：完整离线 profile，追加 Backend/Worker 原 pytest，PC/Mobile 原 lint、typecheck、单元测试及真实 production Vite 配置构建，Electron 原 typecheck 与包含 TypeScript build 的 Node 测试。不运行 Electron 可执行程序或制包。
- `--only`：明确选择完整离线 profile 的子系统，快速检查仍运行。报告明确列出未选择部分，不将其标为通过。
- `--report`：可选的结构化本机结果，包含各步骤耗时、退出码、契约发现、已知未修复项及 NOT_RUN。目录应使用 ignored 本机位置；CI 上传安全报告。

退出码 `0` 表示选定范围检查通过；经审核的精确存量例外仍逐条显示 `KNOWN NOT FIXED`，不表示缺陷已修。`1` 表示新增/扩大差异、失效例外或测试失败；`2` 表示依赖缺失、检查受阻或适用测试跳过。失败与受阻同时存在时返回 `1`，各步骤仍分别记录。命令不自动安装、升级依赖或刷新基线。

缺少依赖时先按原工程规范准备环境，不允许跳过检查凑通过。Backend/Worker 优先使用各自 `.venv`，CI 可使用已安装的系统 Python；`VERIFY_BACKEND_PYTHON`、`VERIFY_WORKER_PYTHON` 只能显式指定 Python 可执行文件，不是另一份连接配置。

## 第一批静态覆盖

权威来源为现有 Backend Enum/Schema。Python 探针仅使用标准库 AST，运行 `-I -S`，不 import 应用。TypeScript 使用已安装编译器解析真实声明、导入类型、联合别名及显示映射的实际初始化对象，不能靠同名文本或类型断言伪造映射完整。

| 覆盖 | 实际使用方 |
| --- | --- |
| TaskStatus、TaskEventType | PC 与 Mobile `entities/task/api/contracts.ts`，并核对两端 TASK_STATUS_META 全状态显示映射 |
| AuditAction、AuditTargetType | PC audit-log 的类型与 ACTION_LABELS/TARGET_LABELS；动作缺少或多出分别报告 |
| WorkerConnectionStatus、SkillClassification | Mobile 设备 DTO，包括 classification 的合法 null；不将 null 当业务类型 |
| OperatingCollectionJobStatus、ItemStatus | 经营页面真实 Collection DTO；另检查后端 Job.kind/status、Item.status/failure_stage 是否真正引用已有权威 Enum |
| AuditLogRead | PC 原始 DTO 全声明字段；ViewModel 只核对明确的 team_id→teamId 映射，不声称自动推导全部业务映射 |
| MyTeamMembershipRead | Mobile HumanTeamMembershipDto |
| DeviceRead、YingdaoProviderInventory、DeviceSkillCapabilityRead、TaskListItemRead | PC 与 Mobile 对应 DTO 的声明字段；数组/对象直接类型、primitive、Literal 和 nullable 兼容性 |
| ErrorResponse | PC/Mobile 公共错误 DTO 的 code、message、request_id 和可空/可选 details |

当前有 10 处 Enum 对照、4 个显示映射、13 处 DTO/显式 ViewModel 对照，以及 4 个后端 Enum 绑定检查。允许真实兼容的宽类型，不强迫两个领域合并成一个状态 Enum。未解析引用或未支持的权威 annotation 明确失败，不静默算一致。

## 第一批动态探针

复用既有正式 ASGI Router、异常处理和现有测试的合成授权/Service override：比较 schedules 缺 timezone、非法 timezone 与普通参数校验的 HTTP 422、错误码及完整 envelope。无数据库或网络服务器。

PC/Mobile 探针直接 import 真实 HTTP client，使用 Axios 内存 adapter，核对正式错误字段、timeout/cancel、HTML 200、detail-only 422 的安全降级、平台错误不得清人员登录态，以及 null/false/0 不混淆。设备探针使用原 mapper 检查未知企业账号状态，不修改 mapper。

观察探针运行通过只说明已得到实际行为；行为是否符合契约由同一次 `verify` 的差异分类与退出码判断。不能把探针测试的 PASS 单独解释为所有客户端已一致。

负向自测在临时源码字符串或内存里增加服务端状态、改变 Literal、缩窄 nullable、删除错误字段及使用不支持的 annotation，经过真实 AST/编译器与分类器后验证子进程非零。业务运行文件保持不变；正常和有意兼容的样本须为零。

## 存量差异管理

`scripts/verify/known-differences.json` 只接受 ca97 审核后的逐条精确签名：rule、contract、expected、actual、reason、review。默认入口输出已知但未修复，不把它们改写成 PASS；严格模式忽略该文件。

没有通配、正则豁免、自动记录或自动刷新命令。新发现或既有 expected/actual 扩大必须失败；已解决的旧例外变为 stale，也必须人工移除/审核。不同使用方、字段及 Literal 值不能共用一条宽泛豁免。确定的产品缺陷交原业务任务单独修复。

## 隔离与未覆盖范围

子进程只收到白名单系统变量及临时合成环境，Backend/Worker 在空 cwd 运行，不读本机 `.env`、真实数据库、Signer、Worker Token 或 Profile。pnpm 子进程使用空 user/global npmrc、离线及关闭版本自动准备。Vite 单测/构建复用原配置，但将 dotenv 目录及读取 cwd 指向空目录；不改默认业务或测试配置。

本机完整离线 profile 明确不运行以下两份会绑定端口的既有测试：

- `backend/tests/test_douyin_signer_runtime.py`
- `backend/tests/test_notification_webhook_e2e.py`

它们是 NOT_RUN，不是通过。原 CI 的 disposable PostgreSQL、完整 Backend pytest、原 Real 前端/Mobile 构建及容器/部署检查全部保留，新增 verify-offline Job 不替换它们，也不改变生产触发边界。

本机不验证 PG Migration、真实平台/数据库/权限链路、容器、原生窗口、安装包或生产。第一版不检查所有 Request DTO、路由、单位/日期业务规则、深层对象 Schema、所有 mapper、Worker/Electron 跨端契约；不会生成全仓客户端或承诺服务端改动会自动更新全部消费方。PC ScheduleRunTriggerResult 的有意子集、联合别名和 sandbox 必需的 IPC 复制不因本检查被一概认定为缺陷。

新增覆盖须登记真实权威和使用方、正常及负向样本，按 Gate 1→ca97 独立 Gate 2→精确 Green/CI→Main Release 推进。生产版本和只读 smoke 仍是后续交付证据，脚本可运行不能代替发布或生产验证。
