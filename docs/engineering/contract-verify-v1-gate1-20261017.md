# Verify 基础接入 Gate 1

Owner 81a1 已实现统一入口、第一批跨端契约防回归、检查器负向自测及 CI 接线。交 ca97 独立 Gate 2，再由 Main 按正式流程发布及只读 smoke；本记录不是全项目契约一致或生产已验证的声明。

## Windows CI 时区返修

原 Candidate `a07529779920d3dcc66198d8eed6f97611fc8900` 的本机与 ca97 独立完整离线结果保留。精确 dev `54513edcfc955b6b4a0887e1e6927924753b98dd` 的首轮 [CI 39021696142](https://github.com/guangyuxu512-cell/AIdashboard/actions/runs/39021696142) 中，原三个 Job 成功，仅 Windows verify-offline 的完整 profile 失败；未重跑该 CI。

Job `117364628422` 的 PC 测试为 781 PASS / 1 FAIL。`shop-mapper.spec.ts:60` 期望 `2026-08-18 18:00` / `19:00`，实际为 `10:00` / `11:00`；28 known、0 new、0 stale，Backend、Mobile、Electron、Worker 通过。ca97 独立读取同一日志确认。既有 mapper 使用本地时区格式化，而 Verify 隔离环境没有固定时区，导致上海本机通过、UTC 显示环境失败。

本次沿原 Feature 正常追加，只在 `scripts/verify/environment.mjs` 对验证子进程设置 `TZ=Asia/Shanghai`，现有 `contracts.test.mjs` 增加一项环境隔离回归，并同步使用说明及本记录。业务 mapper、原测试断言、28 条例外、依赖版本、原 CI 配置和业务运行配置均不变；不修改系统时区。

修前受控 UTC 执行原 mapper 四项测试得到 3 PASS / 1 FAIL，与 CI 两个时间字段的差异逐值相同。新时区自测修前 FAIL（TZ 未定义），修后 PASS：分别以 UTC、America/Los_Angeles 作为传入环境，独立 Node 子进程仍显示 18 / 19，原传入环境保持不变。

| 修后实际入口 | 结果 |
| --- | --- |
| 外层 `TZ=UTC`，`pnpm verify --full --report=…/full-utc.json` | exit 0 / 256.48 秒；28 known、0 new、0 stale；9 Node 自测、2 AST 自测、4 client 探针，Backend 867、PC 782、Mobile 236、Electron 83、Worker 136 及适用 lint/typecheck/Real build 全通过；私有 manager 安装树为空 |
| 外层 `TZ=America/Los_Angeles`，`pnpm verify --report=…/default-los-angeles.json` | exit 0 / 24.74 秒；28 known、0 new、0 stale；无 manager 安装树 |
| 相同外层时区，`pnpm verify --strict --report=…/strict-los-angeles.json` | exit 1 / 23.66 秒；28 failures、0 known、0 stale；无 manager 安装树 |
| 显式不存在的 `VERIFY_BACKEND_PYTHON`，普通入口 | exit 2 / 0.66 秒；契约及其自测 BLOCKED / 未执行；无 manager 安装树 |

两份 MJS 的既有 Prettier、`git diff --check` 和排除路径 diff 检查通过。首次根 `pnpm exec prettier` 因根目录没有该可执行入口失败，随后使用已安装的 Frontend Prettier 检查源码；旧 Markdown 排版检查提示保留，不为本返修全量重排旧文档。工具仍为 Node 24.19.0 / pnpm 11.25.0，项目与 CI pin 未改。新的 Windows Node 22 / pnpm 11.19 hosted CI 交 ca97 在独立 Gate 2 后核验，不以本机成功冒称通过。

脱敏首败摘要与复现入口位于 ignored `.codex/verify-ci-timezone-repair-20261017/`；下载日志在工具内存中筛选，未保存或输出短时下载能力 URL、认证头或 Token。

本次 `full-utc.json` SHA256 `e4901c8cf1bf783839bbda91142f69bf3cc000cc9939b1a03d16b82d956287c3`，默认报告 `b25557e4ff4fd38019c8321efd3101f6e5212e823be02ae24322910a21d6e334`，严格报告 `a8f1aa639ed80fcb7fea5871ee5576ee940d0ce7c315f58b49b112afc58681d7`，缺依赖报告 `23172a427c8a9d20005f8ed8dd03958ab3f47bb4d5890fadcddb2a019aa53d9a`。28 条例外 SHA256 仍为下文原值；业务/依赖/锁/CI/Schema 无改动，本轮无 DB、平台、服务、原生窗口或生产动作。

## 基线与范围

- 分支 `feat/contract-verify-v1` 正常建立于精确 Green `157f9400814aabad574b3d7860ba8bb8a6f00c3b`。Owner 独立 fetch 与读取 CI 39002413981，headSha 一致，原三个 Job 均 success。
- 原经营恢复 3f88、其它 Feature、所有本机材料及共享 stash/Profile 保留。该经营候选已经正常进入上述 Green，不将本任务混回经营或商品 0047。
- 初始可审快照 `14f95920195c84dbeed65b760bd78c9d1773e481` 已推送，例外当时为空，严格检查非零；它不是最终 Gate 1。随后仅正常追加审核例外、验证脚本自身修正及本记录，不改写历史。
- 最终 Candidate 以正式 Handoff 完整 SHA 和本记录所在提交为准。共 16 个验证/CI/文档路径；业务运行源码、原 Vitest/Vite 配置、依赖/锁文件、Schema/Migration、Worker/Electron 运行代码及生产部署触发均无 diff。

## 已实现

根 `pnpm verify` 为快速离线入口，`--full` 追加完整离线 profile；`--strict` 不消费例外，`--only` 明确子系统范围，`--report` 输出安全结构化结果。每步报告状态、耗时和退出码，未运行、缺依赖、跳过都不是 PASS。命令和精确覆盖清单见 [使用说明](contract-verify-v1.md)。

第一批包括 10 处 Enum 对照、4 个实际显示映射、13 处 DTO/显式 ViewModel 对照、4 个经营 Schema 枚举绑定检查，以及正式 ASGI 错误 envelope 与 PC/Mobile 原客户端/mapper 的内存探针。采用已有 TypeScript 编译器和 Python 标准 AST，不导入应用来做静态提取，不生成新客户端或重造测试框架。

Literal、基本类型、直接对象/数组类型、nullable、导入引用和显示对象实际初始化值参与检测。未知或未支持的类型明确非零；真实兼容宽类型可通过。负向样本只存在内存/临时字符串，证明新增状态未补使用方、nullable 收窄、错误字段缺失和不支持注解会使实际命令失败。未改业务运行文件制造测试结果。

子进程环境白名单、空 cwd/dotenv 目录和合成配置覆盖 Backend、Worker、Vite 及嵌套 pnpm。无本机 DB、端口、服务、平台、Profile、安装包或 Migration Slot 需求；没有改变自动执行开关。

## 精确存量例外

ca97 独立复核严格提案 `strict-reviewed-proposal.json`，SHA256 `f8d6feccf11ad41b6d742c15f8375473c73fa862321b3f14c33d883cef47ac52`，批准且仅批准其中 28 个完整 `rule/contract/expected/actual` 签名。Owner 手工逐条加入 `known-differences.json`，含原因、审核日期、Green 及提案 hash；再次对原提案分类为 known=28/new=0/stale=0。

| 已知未修复 | 精确范围 |
| --- | --- |
| 审计动作类型与实际标签缺项 | 六个既有 Access Management 动作，各有类型/显示映射两处，共 12 签名；另 AuditLogReadDto.action 的直接 Literal 收窄 1 签名，与上述同根 |
| 可空值收窄 | Audit DTO.team_id、VM.teamId，Mobile membership_id，PC 嵌套 account_type、enterprise_account，共 5 签名 |
| 枚举绑定覆盖缺口 | 经营 Job.kind/status、Item.status/failure_stage 仍为 str，共 4 签名；不据此声称实际会返回任意状态 |
| 错误 envelope | schedules 缺/非法 timezone 两分支仅返回 detail，共 2 签名 |
| 客户端/映射行为 | Mobile timeout/cancel 未分类、PC 接受 HTML 200、PC 未知 enterprise_account 被折为 false，共 4 签名 |

这些不是本轮业务修复结果。普通入口逐条 `KNOWN NOT FIXED` 并使用限定性结果名称；严格模式仍实跑非零。新增/扩大差异和已失效的旧例外均失败；没有通配豁免、自动刷新或删测试。后续业务修复须在独立任务中审查和核销对应签名。

## 实际验证

最终正确 pnpm 11 隔离下运行，工具实际为 Node `v24.19.0`、预装 pnpm `11.25.0`；项目/CI pin 仍 `11.19.0`，未升级依赖或改 pin。

| 实际命令或步骤 | 结果 |
| --- | --- |
| `pnpm verify --full --report=…/full-no-preparation-final.json` | exit 0，249.76 秒；28 known、0 new、0 stale；私有包管理器安装树检测为空；仅声明的完整离线 profile 通过 |
| Backend 原 pytest | 867 PASS，61.29 秒；376 deselected 属原 marker 边界，另两份需端口的文件明确 NOT_RUN，不冒称真实 PostgreSQL |
| PC 原 lint/typecheck/unit | 全通过；154 文件 782 项 unit；原 Mock 单测模式保持，非浏览器/真实后端证据 |
| PC Real production build | 通过，17.65 秒，复用原 Vite config，仅隔离 dotenv/cwd |
| Mobile 原 lint/typecheck/unit/build | 全通过；29 文件 236 项；production build 3.14 秒 |
| Electron 原 typecheck/test | 通过，含 TS build 和 83 个 Node 测试；未启动 Electron、未制包 |
| Worker 原 pytest | 136 PASS，3.40 秒；未启动真实 Worker 或 RPA |
| 检查器与客户端探针 | 8 Node 自测、2 Python AST 自测、4 客户端观察探针通过；正式 ASGI 三分支仅内存请求，行为差异仍由最终分类器判定 |
| 最后默认入口 `default-final.json` | exit 0，17.66 秒；28 known、0 new、0 stale；没有包管理器安装树 |
| 最后严格入口 `strict-final.json` | exit 1，18.10 秒；28 failures、0 known、0 stale；未通过例外吞掉结果，且无安装树 |
| 明确不存在的 Python 路径 | `missing-dependency.json` exit 2，0.60 秒；契约与自测明确 BLOCKED/未执行，不假装 PASS 或安装依赖 |

完整 profile 后只追加了前置依赖检查分支以避免将依赖缺失误标为自测失败；它已经由最后默认/严格及缺依赖三次实测覆盖。未变的五端检查结果复用，不为输出/前置分支重复运行 782 项页面单测。

原 Starlette TestClient deprecation、Vite 大 chunk 及既有 jsdom 相对图片 XHR 警告保留，不顺手升级库或修改产品测试。契约动态探针使用 ASGI/内存 adapter，不将既有完整单测的回环图片警告写成真实平台成功，也不冒称整个项目全部网络路径已验证。

## CI 和未执行项

只新增 `verify-offline` Job 和安全报告上传。新增 Job 使用 Windows runner，真实执行 Worker 既有三个 Windows-only 单测，不在 Linux 跳过后算完整通过。原 Ubuntu backend/disposable PG/full pytest、frontend/Mobile build、container-runtime 及所有生产触发边界逐字保持。

本机完整离线明确不运行 `test_douyin_signer_runtime.py`、`test_notification_webhook_e2e.py`，因为两者绑定端口；ca97 已审核这一精确 profile 边界，原 CI 完整步骤保留。共享/生产 PG、迁移、容器、平台、原生窗口、视觉 E2E、安装包、生产和新的 hosted CI 均未在 Owner 本轮执行。

第一版不覆盖全部 Request DTO、深层 Schema、所有业务日期/单位、Worker/Electron 的全部跨端契约或所有 mapper，不能宣称全仓自动同步。旧 PC ScheduleRunTriggerResult 有意子集、联合类型别名和 sandbox 必需 IPC 复制不作为自动清理对象。

## 初败与工程修正

- 首轮虚拟 TypeScript 源路径未规范化而未被编译器读取；修正 CompilerHost，保留真实 AST/编译器负测。
- 初版 fieldFindings 只查基本类型/nullable，ca97 独立指出 Literal、对象及 unsupported 三例漏报。已最小补齐并增加端到端子进程非零负测，不修改业务类型。
- Python 临时 cwd 在 Windows 清理时仍被自身占用；已先恢复 cwd 再清理，仅处理本次精确临时目录。
- 初版使用过时的 `npm_config_*`，pnpm 11 实际忽略并在本次私有目录准备了 pin 版本；不能报告整个研发阶段零准备。Owner 核实实际 launcher/官方说明，停止核实归属的测试进程，改用 `pnpm_config_*`、禁自动准备/离线/依赖不齐即错，并增加私有安装树负测和每次实际检测。最终默认、严格、完整报告均检测为空；全局工具和依赖锁文件未改。
- 不存在的旧 `manage-package-manager-versions` CLI 参数及初始失败输出均保留；最终使用真实 pnpm 11 的 `pm-on-fail`。没有靠反复重试绕过工具拒绝或修改测试标准。

## 安全证据与交接

所有安全报告在本工作树 ignored `.codex/contract-verify-v1-20261017/`，不包含平台凭据、会话载荷、真实请求或数据库连接串：

- `default-final.json` SHA256 `fd091246badb2931fa17d463d3c89e1513660d69e6ea1aa373fd8ad6575c0614`。
- `strict-final.json` SHA256 `ce5935b12b36aab32cd1fbec7fd017a82113fad5b6570d353a8b56ffa1adf3cb`。
- `full-no-preparation-final.json` SHA256 `8d5d919a4f2f13aecdcd935c872bee6293cef330e55ee23a534d243ea4cca0cd`。
- `missing-dependency.json` SHA256 `41f144e1660b7d8f513b092e5cd0116268e47432cbf9c893f1f244e435443381`。
- `known-differences.json` SHA256 `4ddacab88bc5a67737a024138ef9f487d6d536b48944092c46ab8ac79258c86b`，只人工录入已批准的 28 条；不是自动生成的基线。

ca97 接收精确最终 Candidate 后独立验证 default/strict/负向/完整离线、例外 diff 和 CI 接线，再走 dev 精确 CI、Main Release 与实际生产版本/只读 smoke。Owner 本轮不合 dev/main、不部署、不连接 Integration/生产，也不要求用户登录、切窗或做机械验收。

回退仅按正常提交回退验证入口/CI增量，不改业务事实、Session、Profile、Migration 或执行配置。此阶段交付状态为工程 Gate 1，不宣称生产验收完成。
