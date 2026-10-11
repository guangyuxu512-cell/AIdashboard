# Shop Login 子窗口自行关闭 — 窄诊断 / 2026-10-11

## 已证实与未知

- 基于原 Candidate `9fc6409c015bec767a5d4a72304a5bb0c0d9e855`，继续原 Feature，保留已通过的 HuanYu 原生登录/留窗/重开证据及数据库成果。发布冻结，未改数据库、Signer、队列、认证或失败策略。
- ca97现场记录：主Electron仍存活；新空测试Profile无`session/refresh`提交，保留NOT_CONFIGURED及释放租约。没有现场Main错误日志，不能据此确定异常类型。
- 受控特征测试复现两条主动关窗链：`loadURL`拒绝→Main关闭；Adapter检测/捕获异常→failed→Renderer取消关闭。主窗口均仍存活、零保存。两次DELETE与两侧清理相容，但不能唯一定位本次现场原因。
- 不把v5旧夹具、ERR_ABORTED、认证失效或平台业务拒绝写成本次根因。加载Promise的失败不等于整应用崩溃；[Electron loadURL契约](https://www.electronjs.org/docs/latest/api/browser-window#winloadurlurl-options)仅用于核对API含义，不是现场证据。

## 本提交只提供取证能力，不冒称修复

Main仅开发模式启用结构化诊断；捕获open/load/detect/capture/refresh、主Frame导航、明确关闭调用及退出/超时。日志不含Error.message、URL、Cookie/Token、店铺身份或平台响应；异常code使用窄字符规则，errno为int32，诊断sink失败不影响原流程。`renderer_request`表示收到Renderer关闭调用，**不直接认定用户主动取消**。没有程序关窗请求时记录`window_closed_without_request`，不编造意图。

启动过滤入口由既有 bundled `pwsh -NoProfile -File electron/tools/capture-login-diagnostics.ps1 -LaunchScript <本工作树.codex内的既有正常启动脚本>` 执行；该 UTF-8 源码不宣称可直接用旧版 Windows PowerShell 的默认 ANSI 解码运行：

1. ca97先核对诊断候选、实际编译SHA、既有5180/8100及唯一开发实例；Owner不切Integration端口或数据库。
2. 用户正常关闭旧开发主窗口，等待全部electron.exe退出。入口检测仍有实例时停止，不自动kill、换端口或启动第二实例。
3. 由ca97提供一次可直接执行的入口：外层过滤脚本调用原正常开发脚本，保留其工作目录、已有人员会话、userData和平台partition，不注入Token，不删除Profile。
4. 仅白名单重建JSONL写入Git忽略位置；stdout/stderr及其他输出不原样存盘或显示。不能另加raw重定向。旧原始ELECTRON_LOG_FILE配置存在时拒绝启动。
5. 只做一次受控空Profile打开检查，无需用户再次登录。读取实际phase/code/errno/Frame状态及关窗原因，再决定最小修复。合成注入异常、旧窗口消失及新工具构建均不是现场根因证据。

正常启动入口中的 Windows GUI 调用本身必须处于内层管道（不能仅在外层将整个 `.ps1` 管道化），并在该调用局部使用 `ErrorActionPreference=Continue`，原样转发双流到外层白名单、保留 native 退出码。不增加日志重定向或新的启动程序：

```powershell
$previousNativeErrorAction = $ErrorActionPreference
try {
    $ErrorActionPreference = 'Continue'
    & node_modules/electron/dist/electron.exe . 2>&1 | ForEach-Object { $_ }
    $nativeExitCode = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previousNativeErrorAction
}
exit $nativeExitCode
```

本机无窗口、无网络的合成 WindowsApplication 验证：直接调用提前返回而子进程仍在；内层管道等待退出、收齐 stdout/stderr，并保留0/7退出码。1024条非白名单输出、畸形JSON、未知阶段及附加字段均丢弃，仅重建9字段。这是启动流测试，不是登录子窗口根因或真实业务验收。

pwsh 的 `ConvertFrom-Json` 会将 ISO `Z` 时间转换为 UTC `DateTime`；过滤器直接保留其 Kind 转换为 `DateTimeOffset`，避免转无时区字符串后误减本地8小时。String输入仍按原规则解析。ca97当前1dec现场日志已有该偏移，只影响记录时间，不能因此认定事件来自8小时前；事件顺序/错误/关窗字段未受影响，不为修正时间打断当前捕获。

Owner只准备代码/过滤入口，不执行启动器、不操作Integration/生产或另开Electron。后续行为修复必须另记真实依据，重新交精确候选及匹配桌面包。原9fc安装包保留，不作为新候选的包。

## 人工取消证据与 closed 诊断缺口

ca97在同一1dec开发实例持续采集后，用户实际打开专用空Profile测试店铺并手动关闭子窗口；主窗口与collector仍在。本attempt最终627条，error/renderer_gone/capture/refresh均0，只有1条`close/request`（`renderer_request`），没有`close/closed`。租约POST201、两次DELETE204，无Session refresh；测试店铺NOT_CONFIGURED v1、HuanYu VALID v3及10Jobs/154Items/0active均保持。此证据支持本次人工取消和释放租约，**未复现原闪退**，历史根因仍未知。

代码核对确认一个可独立复现的诊断缺口：原`report`把可选的原生加载状态读取和sink放在同一try；销毁后的窗口getter或`isLoadingMainFrame`抛错时，整条事件被吞掉。两个定向测试先在旧实现失败（缺closed、缺detect事件）。[Electron closed契约](https://www.electronjs.org/docs/latest/api/browser-window#event-closed)明确要求关闭后避免继续使用窗口；本次没有现场getter异常记录，因此不把合成结果写成现场缺失记录的唯一原因，更不是登录窗口自行关闭的原因。

最小修复只拆分诊断读取：先检查Window未销毁，再尝试获取加载状态，失败时`mainFrameLoading=null`，独立发出原9字段记录。`closed`监听、窗口清理、Renderer取消、身份验证、Session保存及租约代码不动。保留`renderer_request`仅表示Renderer清理调用，不反推用户意图；人工关闭后再由Renderer清理时，合成记录顺序为`closed/window_closed_without_request`然后`request/renderer_request`。

Electron typecheck、build及完整35项测试通过（新增2项，原33项保持）；取消测试仍一次Main DELETE、零capture/save、主窗口存活，捕获及sink失败保护保持。此增量需要匹配提交的桌面包，但不安装、不启动、不打断ca97当前窗口，不要求用户再次登录或点击。原生修正后的closed记录未现场复验，Release继续冻结。

## 定向验证

- Electron `pnpm run test`：33 PASS，含build/typecheck。新增2项原行为特征复现、4项安全阶段诊断；原27项回归保持。
- Frontend `vitest run .../useShopLogin.spec.ts`：9 PASS；只增加failed状态关窗的特征测试，生产Renderer代码未改。
- Frontend完整lint、typecheck及`git diff --check` PASS；PowerShell AST语法检查PASS。过滤器使用合成行单独验证，私密哨兵/畸形JSON/未知阶段均不会原样写入，不启动任何应用。
- 启动工具后续窄增量：UTC `Z` 与 `+08:00` 输入分别配合 native 0/7 退出码，bundled pwsh 4项、PS5显式UTF-8白名单4项PASS；每项等待进程退出、收到2条双流记录、保持正确UTC与9字段。测试PE由PS5编译、两种shell复用（pwsh不支持`Add-Type -OutputType WindowsApplication`）；无窗口、网络或Electron实例。PS5整个中文UTF-8入口仍不宣称直接兼容，实际启动采用bundled pwsh。
- Backend/Schema/正式Frontend生产代码未变，复用原Gate1及ca97独立复验；无新平台、数据库或原生请求。
- 本记录不是Gate2 PASS或现场异常已修复声明。实际诊断及唯一Electron复验由ca97完成，Release继续冻结。
