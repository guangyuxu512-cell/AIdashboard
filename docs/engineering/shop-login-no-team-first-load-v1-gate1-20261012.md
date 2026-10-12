# 店铺无团队登录与首次加载观察 — 阶段Gate 1

2026-10-12，81a1 → ca97。人类授权原始turn `01a13030-2fd6-7990-afb9-ff7e5458c2a1`已回读。
**A代码修复已实现，B仅取证增量，整体PARTIAL；本记录不表示两项原生或生产验收通过。**

## 起点与保留

沿 `feat/shop-login-runtime-diagnostics-v1`，启动HEAD046且clean，仅在Feature FF到精确Green
`22403a1094b25b7569427d5383e4e28154253d79`。main为`db4ca95671348b38dc2d0414ace49a4fab88b181`，
业务树相同，旧046/1279、分支、本地材料、Feature库和安装包均保留。新Candidate由提交后Handoff
登记完整SHA，禁止拿旧046构建结果代替本轮证据。

无Backend运行代码/数据库/Schema/Migration/Signer/经营采集/选品/主题变更，0043不改，无新Slot。
复用专用`control_center_feat_shop_login_session_sync`，本阶段没有数据库写入；Owner纯合成验证，
Frontend4176 strictPort/API全拦截，不使用Integration/生产、不运行平台、不另开或安装Electron。

## A：已确认原因与最小修复

ca97已取正式1.0.5两次entry：bridge/super/platform均true、teamSelected=false，紧接blocked NO_TEAM，
未到IPC。代码也确认前端无条件拦截、IPC UUID强制、Main固定团队头，与Backend真实super全局规则不符。

- `useShopLogin`继续只开放真实UI super能力，team null/空选择归一为undefined；不自动选第一个团队。
- 新Preload常量`globalShopLoginSupported:true`后才允许无团队；旧1.0.5无标记给明确升级提示，
  仍兼容原teamed调用。没有通用版本框架、新IPC或拒绝后重试。
- focus及已有店铺open/recovery允许teamId缺省/undefined；显式null、空串、非法UUID仍拒绝。
  新增Onboarding无recovery仍须团队UUID；保持原新增保存后自动关闭。
- Main已有人员HttpOnly Cookie不变；无团队不发x-team-id，所有metadata/lease/refresh仍经过
  Backend真实super/权限、目标身份、版本/CAS与租约。普通成员或已撤销人员不因少一个头放行。
- 列表/详情共用登录按钮和进度，自动更新、成功留窗/释放、重复点击仅置前、取消/错店/失败
  保留旧Session不变；人员/团队/权限变化仍abort，不增成员关系。

真实无团队验收须使用有效无团队初始会话或正常退出/登录；不注入auth/localStorage/Token，
不新增“清团队”UI。浏览器合成夹具不代表真实权限或生产操作。

## B：已知缺口与旁观增量

旧HuanYu 3fa完整attempt只有637次detect，mainFrameLoading=false，30分钟自然结束；
没有capture/refresh或可靠手动刷新标记。它不能解释遮罩原因，也不能与新attempt拼成同次对照。
当前入口、跳转、脚本、CORS均是未证实排查点，本候选没有换入口、reload、定时刷新、重试或清Profile。

复用原onDiagnostic/固定userData记录器和adapter既有账号探测：

- 仅本attempt WebContents的导航序号、固定路径类别和文档HTTP；序号从0起，导航不证明人工reload，
  ca97须用实际操作时间对照。同次首次打开/刷新保留同一持久化Profile。
- 五个既有固定账号probe顺序/请求/解析不变；只补index→pathClass、HTTP、0～30分钟有界耗时、
  requestFailed。每次最多五项，状态相同仅首条/变化或新导航记录，不存原始结果或identity。
- detect补identityPresent/captureReady/pageContextAvailable布尔。不记录店铺身份、Cookie/Token、
  Header、URL/query、响应或原始异常；未知字段/枚举/非法值仍拒绝。
- 本窗口console只重建固定脚本错误枚举，每主Frame导航至多20项。仅浏览器明确CORS错误才标
  corsBlocked；普通fetch失败保持requestFailed，不猜CORS、过期、风控或平台业务拒绝。
- 不安装session.webRequest hook、不覆盖业务listener、不新增平台请求、CDP/DevTools或任意JS入口。
  成功/取消/超时/窗口结束卸载观察；可选getter/诊断/卸载失败均不改变捕获、保存或释放行为。
- 正式包仍禁DevTools，Origin/主Frame/sandbox/Fuses全部保持；仅扩展白名单读工具可读的字段。

这是观察构建，**首次打开可操作尚未实测，第二项未修复完成**。

## 保存500的独立边界

Main新只读证据：旧d78是MyCookLab，不是HuanYu；refresh到达Backend返回HTTP500/
`SHOP_SESSION_PAYLOAD_INVALID`，随后释放lease。Owner未读任何真实Cookie/payload或原始异常。
静态核对`refresh_service.py`、`auth_context.py`：同码覆盖base64/JSON/Pydantic结构、platform不符、
身份与目标店铺不符、执行期间目标变化等；不能由该码唯一推断结构错或登录过期，更不能当作遮罩根因。
Electron捕获v1字段与正式模型表面对应，无证据不猜解析补丁/放宽目标校验。若新实际流程重现，
须作为保存Gate阻塞，用安全类别进一步定位；旧成功Session和租约保护保持。

## 本阶段实际检查

| 命令 | 结果 |
| --- | --- |
| Frontend `pnpm lint` / `pnpm typecheck` / `pnpm build` | PASS，Real production，既有chunk警告保留 |
| `pnpm exec vitest run` | 142文件629项PASS；定向23项包含其中，不叠加计数 |
| Electron `pnpm typecheck` / `pnpm test` | 50项PASS，包含可选getter/卸载故障保护；早期49项不叠加 |
| `pnpm exec playwright test --config ../.codex/shop-login-runtime-diagnostics/playwright.real.config.ts --output ../docs/_local/shop-login-no-team-first-load-v1/real-intercepted --trace retain-on-failure` | 5项PASS，Real浏览器＋全部API/desktop拦截，没有Backend/平台或原生Electron |
| Backend `.venv\Scripts\python.exe -m pytest tests/test_access_api.py tests/test_shop_session_refresh_service.py tests/test_shop_session_auth_context.py -q` | 17项PASS，既有合成权限/租约/CAS/失败保留契约，无PG/真实平台 |
| `git diff --check`、ignored材料 | PASS；override、截图/log/trace、dist/release不入Git |

早期Electron两项失败分别为测试再次open未先关闭成功保留窗，以及旧断言漏新nav序号；已只修
夹具，不放松去重或白名单。一次Electron目录找不到Prettier，仅改用已安装Frontend二进制，不加依赖。
追加故障getter测试曾有两处返回类型推断错误，补明确测试类型后typecheck及50项全过。
没有运行无关Backend全量、迁移或平台测试。没有安装/启动客户端、没有将合成结果写成原生验收。

## 精确观察交接

提交/推送干净Source后以既有`pnpm run package:win`生成匹配1.0.6NSIS/manifest/checksum，
具体SHA/路径/哈希以Handoff实证为准。保留旧1.0.5安装器和资料，不先替换当前正式窗口。
ca97可从精确候选准备不可变编译快照，复用已核验CookieEncryption兼容44.3.0 SDK与原标准Main `.`
入口，仅登记5180→8100，不改共享SDK/installed/Profile、不另造launcher。Owner不执行入口。
须协调正常串行窗口交接；正式1.0.5现有现场未结束前不能开第二实例或先安装观察包。

匹配reader读取固定userData诊断。先一次first-open，记录可操作性与时间，再由用户在同一窗口
手动刷新一次对照导航/probe/script/readiness。不把两轮attempt混成同次，不用打开罗盘业务面板验收。
第一项无团队、普通成员/撤权、错店/失败保留、自动保存/中控读取仍须新候选真实验证。
确认第二项原因后由Owner按证据最小返修，再整体Gate 2/CI/Release；观察构建本身不能直接收口发布。
Owner不合dev/main、不部署。需要恢复时用旧1.0.5同AppID安装器/固定userData，不清数据或改迁移。
