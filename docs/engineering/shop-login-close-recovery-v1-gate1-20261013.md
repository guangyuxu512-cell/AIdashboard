# 店铺登录修复：关闭恢复 Gate 1

2026-10-13，81a1 → ca97。当前阶段为开发交接，不是生产完成声明。

## 授权、基线与范围

已直接回读ca97人类turn `01a1313b-de4b-7eb1-ba7b-60707e70ce98`，撤销登录Feature暂停。
开工30e8选品恢复树干净；切回保留的`feat/shop-login-runtime-diagnostics-v1`，98d48d4后无遗漏提交。
正常merge精确Green `10938c55397442fd25854d01cf1d07628b7f027b`，合并提交
`4c19b1099542bfae3f06e8b09da5c0577d301985`；仅任务/资源登记冲突，保留双方历史，不rebase/reset。
98观察候选、匹配包、全部旧分支/本机证据、Profile/Session及数据库保留。
选品30e8/86项/原生确认已收口，不重复验收、不混入本轮。

只修同一登录流程的关窗状态恢复与迟到保护，保留98无团队调用/严格权限与窄观察。
无新Backend/API/Schema/Migration/Slot/Signer/选品/经营/达人/调度变更，不调用平台、不写数据库，0042/0043字节不变。

## 已有真实证据及边界

- 98无团队HuanYu关联`a61d0f71-a214-431c-b86c-c0c007222e54`：2026-10-12
  22:52:03.786～22:52:09.189 Asia/Shanghai，身份shop_info_v2 HTTP200，候选权威验证/CAS保存v5→VALID v6、租约释放且留窗，用户原生元数据截图一致。
  此证据不是保存后再经StoredSessionAccessor独立取数成功；若无已有证据，ca97新Gate可复用正式验证会话入口做一次受控核验，不取经营/榜单。
- 首次未登录页用户明确反馈“登录目前不会被加载限制”。没有同次人工刷新对照，不从导航序号猜刷新，历史遮罩根因未确定；不把诊断增量称修好。
- 49da关联`49da1226-4646-4596-b266-4ac89dcbd7e8`：23:49:07.306最后detect:start，
  23:49:07.675 Main真实closed（提前369ms开始检测），27 starts/26 finishes；截至23:50无即时Renderer cleanup、仍“登录中”，Backend租约已释放。
  ca97后来读到00:10:13(+08)的renderer_request/cleanup，距关闭约21分钟；不能写成永久没有任何清理或正常关闭恢复成功。
  原115条归档及安全摘要保留，不倒写、不读取凭据或原始响应。

## 复现与最小修复

新增受控deferred adapter：同一待检测getStatus期间再次focus、真实WindowStub closed，检测保持未决。
**修复前**单项测试FAIL（返回状态尚为undefined而非closed，24.16ms）；**修复后**同一测例PASS（24.76ms）。
这证实共享pending等待路径能造成前端停住；未冒称已确认具体平台fetch为什么没有返回。

- Main保留single-flight，getStatus优先读取终态；每次在途检测与该attempt真实结束状态竞争。
  原生关闭/显式取消/超时/完成结算既有IPC，无新关闭事件通道/额外平台请求/固定刷新。
- 检测返回后先复核attempt/状态/窗口，不继续捕获已关闭尝试；捕获晚到清零Buffer，不保存/映射/复活。
  新店Main主动自动关闭仍保留identified/capture；成功已有店铺仍验证/CAS后留窗。
- Renderer停止轮询后忽略晚到成功/错误，null回复为安全读取失败，不当closed或Session失效。
  Main返回closed且recovery=false时已接管释放尝试，Renderer清忙态和旧focus、不重复释放该租约；远端失败仍由既有到期兜底。
  旧桥接/查询失败和开窗前取消的原清理fallback保留，不扩成租约或重试框架。

## 实际验证

| 位置 / 命令 | 结果与边界 |
| --- | --- |
| electron `pnpm build` + `node --test --test-name-pattern='native close settles an unresolved' dist/tests/management-login-sync.test.js` | 旧实现FAIL，新实现PASS；仅合成Window/adapter/HTTP |
| electron `pnpm test` | 全部54项PASS；含新增4项自然关闭未决检测、显式取消/晚拒绝、晚捕获清零/无保存、未知attempt拒绝，既有Onboarding/CAS/身份/权限/留窗通过 |
| electron `pnpm typecheck` | PASS |
| frontend `pnpm lint`、`pnpm typecheck` | PASS |
| frontend `pnpm exec vitest run src/features/shop-management/model/useShopLogin.spec.ts src/features/shop-management/model/management-login-poller.spec.ts src/features/shop-management/ui/ShopListTable.spec.ts` | 3文件33项PASS，6.11s；闭窗恢复按钮/新登录、焦点迟到不复活、只释放一次、null安全失败/旧VALID保护及原无团队回归 |
| frontend `pnpm exec playwright test --config ../.codex/shop-login-runtime-diagnostics/playwright.real.config.ts --output ../docs/_local/shop-login-close-recovery-v1/real-intercepted --trace retain-on-failure` | 7项PASS，19.4s；Real代码/全部API及desktop bridge拦截；列表与详情同流关窗恢复、无额外保存/重复release、无团队权限。不是Electron或平台实测 |
| frontend `pnpm build` | Real production PASS，19.56s（内含typecheck）；既有大chunk警告保留 |
| 受影响Frontend/Electron文件 `prettier --config .prettierrc.json --check`、`git diff --check`、临时文件/本地覆盖Git忽略 | 最终PASS；初次格式检查FAIL，按既有Frontend格式配置机械整理测试后PASS，33项另复跑；不修改运行逻辑 |

Owner未启动Backend、真实登录窗口或平台请求，未写Feature/Integration/生产数据库；没有重复已通过选品86项及旧安装包验收。
原无团队Backend权限代码相对Green无变化，复用既有真实super授权与合成17项证据，不新造前端权限承诺。

## Candidate、匹配包与 ca97 下一步

最终完整Candidate/clean/push回执、独立1.0.6 Source包路径、manifest/完整SHA256与ASAR复核以正式Handoff为准。
正式包只能从干净已提交树构建；未发布同Feature版本1.0.6保持，不覆盖98观察包或1.0.5回滚包。
ASAR/Fuse/固定AppID/生产Origin/userData/encryption/禁DevTools边界保持；Owner不安装或重启故障实例。

ca97准备新Candidate的匹配Renderer/Main/Preload、唯一Real5180→8100→Integration0043，保留Profile/人员及店铺Session。
只补必要自然关闭/取消→状态按钮恢复、重复focus后关闭/无晚保存，以及成功自动保存留窗和必要StoredSessionAccessor只读核验。
无团队a61和首开可操作证据可复用；三层98或旧选品Renderer不能当新关闭修复验收通过。
新真实Gate2通过才合dev/精确CI→Main Release/生产部署/匹配正式客户端交付及实际运行版本核验。
直到生产“无团队登录→Session更新→中控实际可用”证据取得，不标整个登录任务完成。
回滚沿已有安装器/正常revert流程，保留Profile/Session，不清数据、不降级迁移。
