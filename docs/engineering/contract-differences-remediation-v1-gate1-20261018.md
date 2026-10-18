# Verify 28 项差异修复 Gate 1

Owner 81a1 已从精确 Green `1c4d4e30ab100086e078a17fb9338df3bc5216e4` 逐项修复 Verify 首批 28 个经审核的存量差异。交 ca97 独立 Gate 2；本记录不是 dev/main 合并、Hosted CI、生产发布或真实平台验证声明。

## 基线与边界

- 分支：`feat/contract-differences-remediation-v1`；基线 CI `39113258258` 全部成功，生产 `845f142` 仅作为已发布事实保留，本任务没有新的生产发布授权。
- 修前默认 Verify：exit 0，精确 28 `KNOWN NOT FIXED`、0 new、0 stale；修前 strict：exit 1，精确 28 failures、0 known、0 stale。
- 原经营会话候选 `a6f4bde7105cff3ad2ac292fb8e5db0f091fd38a`、其它分支、Profile、stash 和本机材料未改动；没有数据库、Schema、Migration、平台请求、端口、服务、Electron 窗口或安装包操作。
- 仅修权威 Backend/PC/Mobile 契约与真实消费路径；没有修改 Verify 的 expected、分类规则或负向测试来迎合实现，也没有新增例外。

## 分组修复

| 提交 | 已核销差异 | 根因与修复 |
| --- | ---: | --- |
| `b797128` `fix(audit): align access action contracts` | 15 | PC 审计动作联合和显示映射漏掉后端已有的六个 Access Management 动作，DTO/VM 又将全局审计的 `team_id` 收窄为必填。补齐类型、筛选项与中文标签，保持团队为合法 `null`，并覆盖超级账号审计映射。 |
| `3d21b9a` `fix(clients): preserve nullable identity state` | 4 | Mobile 超级账号的 membership 可以为空；PC 影刀嵌套账号类型和企业账号标志可以为空，mapper 又把未知企业账号折为 `false`。DTO/VM 全链路保留 `null`，明确区分未知与真实否。 |
| `f3a31c4` `fix(operating): bind collection read enums` | 4 | 经营采集读模型使用任意 `str`，未绑定已有权威枚举。Job kind/status、Item status/failure_stage 改为既有 StrEnum，`failure_stage=None` 仍合法，未知值由 Pydantic 拒绝。 |
| `836c566` `fix(schedules): unify query validation envelope` | 2 | Schedule 查询手写 `HTTPException(detail=...)` 绕开统一异常包络。新增最小查询模型与依赖，复用 `RequestValidationError` 处理，使缺少/非法 timezone 均返回 `VALIDATION_ERROR`、message、request_id 和安全 details。 |
| `e4c0373` `fix(clients): enforce runtime response contracts` | 3 | Mobile 未区分 Axios 超时/取消；PC 普通 JSON 请求接受 HTML 200。补齐 `REQUEST_TIMEOUT` / `REQUEST_CANCELLED`，PC 普通请求只接受 JSON/204，同时保留显式 Blob/ArrayBuffer/Stream 文件响应；这些错误不触发 Human Session 失效。 |

`scripts/verify/known-differences.json` 随每组实际修复逐步从 28 → 13 → 9 → 5 → 3 → 0；每一步默认 Verify 均为 0 new、0 stale。最终文件为 `[]`，没有通过新增、扩大或自动刷新例外清零。

## 定向验证

- PC 审计 DataSource 3 项通过，含全局 `team_id=null` 和六个新增动作标签；Frontend typecheck/lint 通过。
- Mobile Human Auth DataSource 3 项通过，含 `membership_id=null`；PC Device mapper 9 项通过，含未知企业账号保持 `null`；两端 typecheck/lint 通过。
- Backend 经营 API 7 项通过，含合法枚举序列化、`failure_stage=None` 与未知 stage 拒绝。
- Backend API 21 项通过，Schedule 成对参数、缺 timezone、非法 timezone 的统一 422 包络均验证。
- Mobile API Client 8 项通过；PC HTTP Client 与资产下载 10 项通过。HTML 200 被安全拒绝，JSON、204 与 Blob 仍成功，平台/传输错误不会清除人员登录态。
- 所有修改后 `compileall`、`git diff --check` 及受影响 lint/typecheck 通过；未执行项不会标成 PASS。

## 最终 Verify 与完整离线档案

工具使用已登记 Node `24.19.0`；Verify 内实际项目包管理器 `11.19.0`，项目 pin、依赖和锁文件未修改。结构化报告仅保存在 ignored `.codex/contract-differences-remediation-20261018/`。

| 实际入口 | 结果 | SHA256 |
| --- | --- | --- |
| 修前默认 `baseline-default.json` | exit 0 / 21.63 秒；28 known、0 new、0 stale | `3e3e66df28491fc50dcd7e4024f7054a66c013e2c247a24796c7f48b9f24bd67` |
| 修前 strict `baseline-strict.json` | exit 1 / 17.61 秒；28 failures、0 known、0 stale | `77f01f26123d803967a1fb407f9cb7a617689c7d9871f64bd39be8573006c3ec` |
| 修后默认 `final-default.json` | exit 0 / 17.95 秒；0 known、0 new、0 stale | `5d672af56c26e47c517a166ed9de977d7eed3416b3c6b5f7ac52447d00142c73` |
| 修后 strict `final-strict.json` | exit 0 / 17.66 秒；0 known、0 new、0 stale | `38e2fe28c72a9d64cdc90fef81adb3f4f24bc5a3dee0a8108c0649b87a844d56` |
| 修后完整离线 `final-full.json` | exit 0 / 265.81 秒；0 known、0 new、0 stale | `3b35facda6e61ac74c42f2dad3cc07404e71bfd4d53659809f5e0fe4e98975ff` |

完整离线 profile 结果：Backend 1049 PASS（442 deselected，仍遵守原 marker/端口边界）、PC lint/typecheck/169 文件 929 项/Real production build、Mobile lint/typecheck/29 文件 238 项/Real production build、Electron typecheck/83 项、Worker 136 项全部通过。检查器 10 个 Node 负向自测、2 个 Python AST 自测以及正式 ASGI/客户端探针通过；受控的新增状态、nullable 收窄、错误字段缺失、品牌 wire 交换等变异仍返回非零。

既有 Starlette deprecation、jsdom 相对图片 XHR、Naive 注入和 Vite 大 chunk 警告保留，不借本任务升级依赖或重构无关模块。完整 profile 明确 NOT_RUN：本地/共享/生产 PostgreSQL 与 Migration、容器/runtime、真实平台、原生 Electron/视觉 E2E，以及两份会绑定端口的 Backend 测试；原 CI 保留这些边界。

## 交接与回退

ca97 接收精确最终 Candidate 后，独立复核五个分组提交、空例外文件、默认/strict/full Verify 和负向变异；再决定后续 dev/CI/Release。Owner 不合 dev/main、不部署，也不把离线 Gate 1 写成生产完成。

每组均为独立可回退提交。若回退某一业务提交，必须同步恢复其精确已审核差异记录，不能只回退运行代码而留下错误的零例外声明；无需回滚数据库、Session、Profile 或部署配置。
