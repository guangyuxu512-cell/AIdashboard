# Shop Login Runtime Diagnostics V1 — Gate 1

2026-10-12，81a1 Feature Owner → 集成ca97。本候选提供安全观测与交互保护，**不是已定位生产根因**。

## 授权、基线和范围

- 已只读核验ca97的人类原始turn `01a12c59-4ac4-70f0-894d-5aed7cd7731c`，授权最小诊断与打开反馈。
- Branch：`feat/shop-login-runtime-diagnostics-v1`。
- 精确Green：`1718abe117c90842c8d39859a074fa988360f070`；提交前远端dev仍为同一SHA。
- Candidate与实际安装包Source SHA在提交后的正式Handoff/manifest中记录，不把未提交工作树称候选。
- 保留旧分支、ignored材料、Feature库及选品恢复候选`1279cc9ee71eaab52c0a76e86940edac12f53d0d`。
  选品候选未混入本提交；其普通/最大化Electron尺寸复验仍单独待ca97，不能因本候选通过而算通过。
- 无Backend/DB/Schema/Migration/Signer/平台请求变更，无Slot；0042/0043不改。
  不停止或重启唯一生产故障Electron，不创建第二个Electron，不读生产Profile/凭据或改服务器配置。

## 复用和实际改动

复用ManagementLoginService/onDiagnostic、窄focus/open IPC、原人员HttpOnly认证、Profile、
Refresh Lease、CAS保存、startManagementLoginPolling、useShopLogin、AppButton和列表/详情注入。
不新增登录程序、Session系统、通用日志/插件/版本框架或公共控件。

1. 在既有登录业务中增加一次点击随机UUID。Renderer记录入口布尔值、focus/lease/open/cleanup；
   IPC和Main记录focus→认证准备→GET实际发出→open及原load/detect/capture/refresh/close。
   认证准备开始不等于GET已发出，GET request事件只有认证头准备成功、fetch调用前才出现。
2. Main固定用途记录器同时适用于正式包。主WebContents、主Frame、来源与当前精确Origin、
   固定前缀和2048字符上限均检查；未知字段/非法值拒绝。文件只含随机关联ID、枚举、布尔值、
   HTTP状态、耗时、安全code/errno，不含人员/店铺/团队ID、Cookie/Token、URL/Header、payload或原始Error。
3. 固定userData的`diagnostics/shop-login.jsonl`，512KiB/份及单一`.1`轮转，待写128项；
   写入错误不影响登录。读取工具只读固定两份文件，重建白名单且最多输出最近200条；不进ASAR。
4. Main元数据15秒及open30秒总时限；Renderer focus20秒、lease20秒、open35秒。
   lease仍服从原HTTP Client10秒时限。取消/上下文改变/超时立即恢复点击，迟到响应不再开窗或保存。
   HTTP401/人员Cookie缺失、403、HTTP、网络、超时分别表达；未知错误不声称平台Session过期。
5. 列表和详情共用opening/focusing反馈。开窗前、置前请求中阻止重复；等待人工登录时仍可点击，
   经原focusShop复核当前权限，只置前，零新增lease/open/save；置前超时不取消进行中的捕获。
   原成功留窗、首次Onboarding成功关闭、失败不清旧Session/Profile均保留。
6. 发布兼容：新Preload常量`managementLogin.correlationSupported: true`明确支持后才附加字段。
   旧1.0.4没有标记，仍传原白名单；不遇拒绝后盲重试，不放宽Main参数/Origin/Frame检查。
   完整一次点击关联须候选Renderer＋新Main/Preload匹配。旧客户端与新服务器不能因新增参数自行故障。
7. Electron版本1.0.5，固定AppID/userData、生产Origin、全部安全开关和Fuse不变。正式DevTools仍禁用。

## 实际验证

Node采用既有受管运行时24.19.0；无新依赖。以下在81a1环境执行：

| 命令 | 结果与边界 |
| --- | --- |
| Frontend `pnpm lint` / `pnpm typecheck` | PASS；最后E2E夹具修正后复跑PASS |
| `pnpm exec vitest run` | 142文件627项PASS；早期625项及定向21项不重复相加 |
| `pnpm exec vitest run src/features/shop-management/model/useShopLogin.spec.ts src/features/shop-management/ui/ShopListTable.spec.ts` | 2文件21项PASS，包含新/旧bridge、active只置前、重复/超时/迟到/撤权及真实AppButton禁用恢复 |
| Frontend `pnpm build` | Real production PASS，既有大chunk警告保留，不做无关性能重构 |
| Electron `pnpm typecheck` / `pnpm test` | PASS，43项；包含packaged记录器、Preload固定标记、Origin/Frame/字段拒绝、15秒/迟到保护、DNS/errno和原同步生命周期 |
| `pnpm exec playwright test --config ../.codex/shop-login-runtime-diagnostics/playwright.real.config.ts --output ../docs/_local/shop-login-runtime-diagnostics-v1/real-intercepted-verified --trace retain-on-failure` | 3项PASS，1366×768 Real浏览器，全部API与desktop能力合成拦截，没有Backend/平台请求或真实Electron |
| `git diff --check` / Git ignored材料核查 | PASS；本机override、测试日志/截图/trace、dist/release均ignored，不提交 |

E2E实际覆盖列表/详情登录同步与成功留窗后只置前、capture等待阶段共享按钮、置前阶段禁用、
取消恢复/释放及普通团队无入口。最早一次新增夹具因Naive加载图标改变可访问名称而失败；改为
匹配文字末尾后，下一次因遗漏取消的DELETE lease拦截失败。已补既有DELETE契约并断言恰好一次
POST及取消DELETE，最终3项全过。早期unit typecheck也发现3处可选focusShop测试类型断言，修正后
上述lint/typecheck/build通过。没有通过修改业务、放松权限或吞异常来“修过测试”。

未运行Backend/PG/平台/迁移测试（无对应改动）；未进行生产实际点击、原生真实登录、安装升级、
标准窗口操作或用户Profile读取。截图`docs/_local/shop-login-runtime-diagnostics-v1/real-intercepted-verified/`
为真实代码的浏览器＋合成API，不是Electron/平台证据。

## 精确交接与Gate 2

Owner提交并推送干净Feature后运行既有`pnpm run package:win`，只生成匹配Source的NSIS、manifest、
checksum，交付`D:\中控台\dist\desktop\1.0.5-<Candidate12>\`。构建复跑Electron43项、官方artifact
checksum、Fuse/ASAR/PE检查；实际路径/哈希/大小以正式Handoff的成功结果为准，不提前称已构建。
先保存旧manifest/checksum和旧安装器，禁止覆盖回滚材料；不安装、不替换运行中的故障现场。

ca97对精确候选只读审查后，在唯一匹配Real Electron核对人员/团队、一次实际点击及白名单链，
先指出第一个停点，再验证打开/自动同步/留窗/置前/取消/失败恢复。完整链须匹配Renderer及桌面包，
旧版本缺记录、工具无法实际点击、浏览器合成通过均不能写成根因确定。
保持原故障窗口和Profile直到ca97按人类授权安排取证/升级；不得以打开罗盘页作为店铺登录成功前置。
Gate 2、精确dev CI及Release Gate由ca97/Main执行，Owner不合dev/main、不发布生产。

## 回滚与限制

本候选可revert业务专用提交；已安装版本用校验通过的旧1.0.4安装器回滚，AppID、userData和Cookie
encryption不变，不清数据、不改迁移。新Renderer兼容旧bridge，回滚不需要开放额外参数或调试。
生产原故障尚未取得实际点击证据，**根因未确定**。本次只使停点可观察、等待可反馈，并保留权限与
同步保护；不能宣称“现网登录已修复”“选品前端原生已验收”或“所有发布完成”。
