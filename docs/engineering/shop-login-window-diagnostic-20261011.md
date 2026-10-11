# Shop Login 子窗口自行关闭 — 窄诊断 / 2026-10-11

## 已证实与未知

- 基于原 Candidate `9fc6409c015bec767a5d4a72304a5bb0c0d9e855`，继续原 Feature，保留已通过的 HuanYu 原生登录/留窗/重开证据及数据库成果。发布冻结，未改数据库、Signer、队列、认证或失败策略。
- ca97现场记录：主Electron仍存活；新空测试Profile无`session/refresh`提交，保留NOT_CONFIGURED及释放租约。没有现场Main错误日志，不能据此确定异常类型。
- 受控特征测试复现两条主动关窗链：`loadURL`拒绝→Main关闭；Adapter检测/捕获异常→failed→Renderer取消关闭。主窗口均仍存活、零保存。两次DELETE与两侧清理相容，但不能唯一定位本次现场原因。
- 不把v5旧夹具、ERR_ABORTED、认证失效或平台业务拒绝写成本次根因。加载Promise的失败不等于整应用崩溃；[Electron loadURL契约](https://www.electronjs.org/docs/latest/api/browser-window#winloadurlurl-options)仅用于核对API含义，不是现场证据。

## 本提交只提供取证能力，不冒称修复

Main仅开发模式启用结构化诊断；捕获open/load/detect/capture/refresh、主Frame导航、明确关闭调用及退出/超时。日志不含Error.message、URL、Cookie/Token、店铺身份或平台响应；异常code使用窄字符规则，errno为int32，诊断sink失败不影响原流程。`renderer_request`表示收到Renderer关闭调用，**不直接认定用户主动取消**。没有程序关窗请求时记录`window_closed_without_request`，不编造意图。

启动过滤入口 `electron/tools/capture-login-diagnostics.ps1 -LaunchScript <本工作树.codex内的既有正常启动脚本>`：

1. ca97先核对诊断候选、实际编译SHA、既有5180/8100及唯一开发实例；Owner不切Integration端口或数据库。
2. 用户正常关闭旧开发主窗口，等待全部electron.exe退出。入口检测仍有实例时停止，不自动kill、换端口或启动第二实例。
3. 由ca97提供一次可直接执行的入口：外层过滤脚本调用原正常开发脚本，保留其工作目录、已有人员会话、userData和平台partition，不注入Token，不删除Profile。
4. 仅白名单重建JSONL写入Git忽略位置；stdout/stderr及其他输出不原样存盘或显示。不能另加raw重定向。旧原始ELECTRON_LOG_FILE配置存在时拒绝启动。
5. 只做一次受控空Profile打开检查，无需用户再次登录。读取实际phase/code/errno/Frame状态及关窗原因，再决定最小修复。合成注入异常、旧窗口消失及新工具构建均不是现场根因证据。

Owner只准备代码/过滤入口，不执行启动器、不操作Integration/生产或另开Electron。后续行为修复必须另记真实依据，重新交精确候选及匹配桌面包。原9fc安装包保留，不作为新候选的包。

## 定向验证

- Electron `pnpm run test`：33 PASS，含build/typecheck。新增2项原行为特征复现、4项安全阶段诊断；原27项回归保持。
- Frontend `vitest run .../useShopLogin.spec.ts`：9 PASS；只增加failed状态关窗的特征测试，生产Renderer代码未改。
- Frontend完整lint、typecheck及`git diff --check` PASS；PowerShell AST语法检查PASS。过滤器使用合成行单独验证，私密哨兵/畸形JSON/未知阶段均不会原样写入，不启动任何应用。
- Backend/Schema/正式Frontend生产代码未变，复用原Gate1及ca97独立复验；无新平台、数据库或原生请求。
- 本记录不是Gate2 PASS或现场异常已修复声明。实际诊断及唯一Electron复验由ca97完成，Release继续冻结。
