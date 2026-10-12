# 店铺登录修复：Gate 2（2026-10-13）

## 结论与版本

Gate 2 PASS；精确 dev CI、Main Release、安装及生产验收仍独立推进，不是 DEPLOYED 声明。

- Owner：81a1；Integrator：ca97；发布执行者：正式 Main。
- Candidate：`ce3e488bce0f8bb8f54671a792c01aa83938a92e`，分支 `feat/shop-login-runtime-diagnostics-v1`。
- Green 基线：`10938c55397442fd25854d01cf1d07628b7f027b`；正常 no-ff Merge：`0890a5255469b47a2e593290839af549b0541d64`。
- 包含保留的98候选；Owner正常同步Green的Merge为`4c19b1099542bfae3f06e8b09da5c0577d301985`。整体审查相对Green的26文件，不只审最后的关闭修复。
- Backend、Worker、Mobile、Signer、选品运行代码与依赖无变化。无Schema/Migration/Slot，单一`20261010_0043`不变。
- 已通过选品86项及人工视觉证据保留，不重复验收；罗盘经营/收支面板不属于本轮条件。

## 修复与真实证据

无团队超级账号经新Preload固定能力标记进入现有店铺登录，无团队不发`x-team-id`，不自动选团队、不新增成员。Backend真实人员权限、目标身份、租约、版本CAS仍权威；普通成员与新店Onboarding团队要求不变。

关闭修复仍single-flight；真实关闭/取消/超时/完成立即结算在途状态，迟到检测不捕获、迟到payload清零且不保存或复活。前端停止后不处理晚到结果，Main已接管的清理不重复释放。没有新关闭IPC、固定刷新、通用恢复框架或Profile清理。

实际为唯一Real Electron，`5180 → 8100 → control_center_integration`，`g2_sa_v1_super`启用且超级账号。Renderer/Main/Preload都来自精确ce3e归档，不用选品Renderer与旧登录壳混搭判断。固定Profile、人员会话和店铺Session保留。开发Main PID63132、5180 PID36352、8100 PID103868；Signer8787和受信任35433隧道复用，监听loopback、Vite strictPort。主窗口“电商 AI 中控台”，页面`http://127.0.0.1:5180/#/shops`。

用户在本次匹配环境回复“验收通过”。原生捕获报FrameArrived timeout、索引点击报coordinate input geometry unavailable，由用户实际点击，不以网页截图替代原生证据。

| 项目 | 证据与结论 |
|---|---|
| 新候选自然关窗 | 关联`cac6488a-8751-4686-8d24-0d884813b92a`：2026-10-13 02:49:34.404 +08 native closed，02:49:34.693 renderer cleanup finish，约289ms。随后原生可访问树显示测试行“登录”可点击，不再“登录中”；子窗已消失。 |
| 无团队入口 | 同次entry为superAccount=true、teamSelected=false，bridge/platform可用，GET metadata 200、租约/open成功。匿名取消样本不冒充真实店铺认证。 |
| 取消保护 | 既有`G2-ShopLogin-Cancel`无真实平台身份，取消后仍not_configured v1、无活动租约，没有迟到保存；没有新建夹具店铺或凭据。 |
| 正确店铺自动保存、留窗 | 复用未变路径的匹配98真实关联`a61d0f71-a214-431c-b86c-c0c007222e54`：HuanYu无团队验证目标后v5→valid v6、租约释放、浏览窗保留，用户原生详情确认时间/版本。没有宣称本次生成v7。 |
| 已保存Session实际可用 | 2026-10-13 02:57:33 +08，既有Integration只读检查从stored v6走`ShopSessionAccessor → DouyinPlatformConnector → shop_info_v2`，业务成功且243321624/HuanYu身份匹配。1必要只读平台请求、0业务写入、无响应Cookie回存；这是正式读取边界检查，不冒称用户再次点击HTTP健康检查。 |
| 首开可操作 | 复用此前人类“登录目前不会被加载限制”及匿名页可操作确认。历史遮罩唯一根因仍未知，未取得同次首开/人工刷新对照，不把观察日志或新SHA冒称根因修复。经营面板错误不是登录认证失败证据。 |

HuanYu Integration Shop ID为`c448f225-b141-409b-bc94-12f1ae74ee04`，当前valid v6、无活动租约。经营Job10/Item154/活动Item0不变，无榜单或经营采集。错店、失败保留旧Session、成员守卫、新店自动关闭和迟到捕获为受控测试证据，与上述真实场景分开记录。

## 独立检查与合后复验

候选归档独立54 Electron、33前端、lint/typecheck/Real build、正式包ASAR/source/Fuses通过。Owner7项完全拦截的Real前端/API/桥接测试仅补充，不替代原生平台证据。

合并后Frontend/Electron/Backend/Worker/Mobile与ce3e字节相同，在实际dev再执行：

- Electron：`tsc -p tsconfig.json`、`node tools/run-tests.mjs`，54/54 PASS。
- Frontend：useShopLogin/management-login-poller/ShopListTable三个文件，33/33 PASS。
- 受影响文件ESLint、`vue-tsc --noEmit -p tsconfig.app.json`：PASS。
- `VITE_API_MODE=real vite build --mode production`：PASS，16.85s；仅既有大chunk提示。
- Backend权限/Session未变测试复用，不申请库或执行迁移。

Git、ignored临时材料、`.dev-runtime`和真实进程核对；历史Main偏置PID记录不作为当前服务事实。脚本/日志/截图/配置/build/test产物ignored，不提交凭据、完整请求或原始平台响应。

## 匹配客户端与发布边界

必须升级1.0.6 Main/Preload，服务器Renderer发布不能代替客户端交付。

- Source：`ce3e488bce0f8bb8f54671a792c01aa83938a92e`。
- 安装器：`D:\中控台\dist\desktop\1.0.6-ce3e488bce0f\Siyu-AI-Control-Center-1.0.6-ce3e488bce0f-windows-x64-setup.exe`，120310140 bytes。
- Installer SHA256：`12fcc2e20dcd238979a6be661e487bdf4b779ea6d9f2ac202d12375a1bae7888`。
- ASAR SHA256：`6fe653e678fc6d15dec678053a7975a5a374d38d1306383bd0d0be2f58db78fc`。
- source/version/关闭结算/globalShopLoginSupported及9项Fuses独立PASS；固定AppID/userData/HTTPS Origin/Profile不变，测试/工具未打包。
- NSIS per-user x64，NotSigned，手动升级，无自动更新；旧1.0.5/98包保留，新包未安装。

精确dev CI全部成功后登记Green并交Main Release Gate。Main按既有备份/恢复规范完成main CI与自动部署、匹配安装器交付、实际客户端版本及生产无团队登录→Session更新→正式读取验收，完成前不标DEPLOYED。

无迁移，不降级0043，不改变每日采集配置；失败按正常revert/旧安装器恢复，不重置Profile或有效Session。历史首载/旧生产无反应根因未确定的事实保留，不以还原历史根因扩大已通过最小流程的门槛。
