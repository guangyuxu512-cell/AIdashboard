# Verify 独立集成验收

ca97接受候选 `a07529779920d3dcc66198d8eed6f97611fc8900` 的离线Gate 2；基线为Green `157f9400814aabad574b3d7860ba8bb8a6f00c3b`。尚待正常no-ff、合后复验及精确dev CI，不能据本机结果标Green或已部署。

## 范围与已知差异

本次16个路径仅增加统一verify入口、跨端契约检查、负测、CI及文档。Backend/PC/Mobile/Electron/Worker运行代码、迁移、依赖锁文件及生产触发器与Green一致；没有DB、端口、平台、Profile、安装包或额外Electron需求。

覆盖10组权威枚举、4组实际映射、13组DTO和4项枚举绑定。使用Python AST及TypeScript编译器读取实际代码，正式ASGI和PC/Mobile内存客户端探针补运行契约；未覆盖全仓全部业务语义，不能替代各Feature真实闭环。

28个精确存量签名已由ca97逐项批准为“已知未修复”：审计动作及DTO收窄13项、nullable收窄5项、经营枚举未绑定4项、Schedule错误包络2项及客户端运行差异4项。例外没有通配符，不自动刷新；新增、扩大和失效均拒绝。严格模式不使用例外，仍失败。审核文件SHA256为 `4ddacab88bc5a67737a024138ef9f487d6d536b48944092c46ab8ac79258c86b`，与批准版本完全一致。

## 独立实际结果

使用精确Git归档、现有锁定依赖的私有离线布局、bundled Node24.19.0及实际pnpm11.25.0；声明pin11.19.0未修改，CI继续按pin执行。Python显式使用既有解释器，仅加载归档源码；Worker解释器只读复用81a1原venv，不以其工作树为测试cwd。

| 检查 | ca97结果 |
| --- | --- |
| `pnpm verify` | exit0，20.07秒，28 known、0 new、0 stale |
| `pnpm verify --strict` | exit1，19.64秒，28 failures、0 known、0 stale |
| 明确不存在的Python路径 | exit2，未执行的契约/自测明确BLOCKED |
| 负向自检与探针 | 8 Node、2 Python AST及4客户端观察通过；含Literal/对象/unsupported差异真实非零、缺字段、nullable、枚举缺失、例外扩大/失效和私有包管理器安装树检测 |
| `pnpm verify --full` | exit0，349.48秒，仍28 known；适用步骤无FAIL/INCOMPLETE/BLOCKED |
| Backend | 867 PASS、376 integration deselected；原marker边界保持 |
| PC | lint/typecheck、154文件782 unit通过；Real build22.96秒 |
| Mobile | lint/typecheck、29文件236 unit通过；Real build3.75秒 |
| Electron | TS/typecheck、83 Node测试通过，未启动客户端或打包 |
| Worker | 136 PASS，包含Windows适用项，未启动真实Worker/RPA |

完整离线明确NOT_RUN：共享/生产PG、迁移、容器、平台、原生及视觉E2E，以及会绑定端口的 `test_douyin_signer_runtime.py`、`test_notification_webhook_e2e.py`。原CI完整Linux/PG/容器Job保留；新增Windows `verify-offline` Job尚待托管运行，不能把本机结果冒充CI。

verify调用使用空临时用户/cwd、受限环境、已有依赖和无dotenv的Vite配置，私有包管理器安装树检测均为空。前置依赖准备为已有store的 `--offline --frozen-lockfile --ignore-scripts`，没有改锁、联网安装或改运行资源；不宣称整个准备阶段从未建立依赖布局。

## 准备失败与保护

初次归档将node_modules接到另一workspace，pnpm一致性检查在测试前拒绝；独立私有布局解决，未关闭检查。随后PATH误用系统Node20.18，pnpm缺少node:sqlite，客户端探针未执行，报告失败及4条stale；明确固定已有Node24.19 PATH后默认/严格/完整均实测。初败日志/报告全部保留，不计入通过，不修改候选业务。

没有读取ignored环境值、生产凭据或平台Session；代码/合同所用合成值不代表真实业务成功。现有Integration47、真实751商品快照、经营事实、用户Profile、共享stash及8100/5180服务不因Verify验证改变。

## 证据与发布边界

原始报告位于ca97忽略的 `.codex/gate2-contract-verify-a0752977-utf8/`：

| 报告 | SHA256 |
| --- | --- |
| default-independent-node24.json | 73c153208ece67e9add69a6935d83aedf5d3922cc70e2c9a4f94035cdd952245 |
| strict-independent-node24.json | 1045e7f130d6378bbeedc6683724095ed7b692845ef3ae618e2c926176464128 |
| full-independent-node24.json | fcf4bb232195e372bedfeb75be34aa5b1d192fd9ee609f2375cddb2cca163742 |
| missing-python-independent.json | e275a727ab1bb5f2ccfb5d17443c5977c3e63cf18dffd33b55c66130c99fa525 |

Integrator按原流程合并、复验、推送dev及等待全部精确CI。通过后交Main Release Gate；生产部署须等ca97当前固定8项经营恢复终态/无在途交接，不能并行切换镜像。Verify无Migration，生产维持单一0046及现有09:00计划；不把未合的商品0047带入本Release。

回退仅正常revert入口/CI增量，保留共享历史、业务事实及既有配置；不重置工作树、Profile、数据库或已应用迁移。
