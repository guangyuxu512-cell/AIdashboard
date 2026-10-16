# 店铺登录刷新拒绝与人工继续 Gate 1

2026-10-16，81a1 → ca97。本候选修复刷新失败后提前关窗和失效租约无法继续的问题，
增加安全的拒绝分层；MyCookLab实际载荷拒绝子分支仍待匹配版本取证，不能据此宣称真实登录已恢复。

## 基线与范围

已直接回读规划人类`01a14500-90c2-7b42-8a11-5ccba24ee1a6`及上下文。ca97明确批准从已发布
功能Green`1773a97d27c56512a620337e3259cceabadca2f1`建立`feat/shop-login-refresh-recovery-v1`。
该基线精确CI38789232361三Job成功；不混尚未批准发布的清理1aec/Green5a18或7d55。
精确Candidate、clean/push回执及匹配Source包以本次正式Handoff/manifest为准。

## Gate 2 退回后的定向返修

首候选`48dd4c8988786dcc0e56868704751119556e6150`被ca97独立源审退回，不能作为完整Gate2候选。
原39项前端检查未覆盖续租失败后的关闭：立即拒绝及超时后停止了窗口观察，关窗后busy仍在；
原候选还将固定登录入口改名并在受阻时禁用，违背原交互。Owner在旧实现上复现这两类关闭失败和入口失败后修复，
保留48dd源码、1.0.7旧Source包、原验证及ca97独立失败记录，不倒写成通过。

新的观察复用原轮询，在续租等待期间及拒绝/超时后只读Main failed/closed；成功取得新租约、可以重新open时才停止。
观察不自动refresh/capture，不覆盖续租错误、不改变canContinue、不重复toast。关闭时取消当前flow，
不能用描述旧Main租约的recovery=false把Renderer新租约标成已释放；超时回执只释放自身，并受代次/人员检查。
列表与详情恢复固定“登录”及原瞬态；可继续时沿新租约流程，次数/权限受阻时仅置前、不续租或重发，取消入口保留。
新增立即拒绝、超时、pending期间关闭/取消/换人员、迟到租约不影响后续lease、受阻置前及详情实际按钮事件回归。
后端/Schema/迁移/IPC字段和三次上限相对48dd不变；复用已独立通过的27项Backend和包身份边界，
新Source仍按1.0.7独立目录构建，不覆盖旧包、不安装或启动。MyCookLab实际拒绝子分支仍未知。

只改既有Session refresh校验分层、Main/Preload/status契约、原列表/详情登录反馈及定向测试。
沿用ShopSession、原租约、权威验证、CAS、Profile映射、窄IPC及既有轮询；无新登录系统/队列/框架。
选品A/B、已确认界面、Connector/Signer、经营恢复、权限/API路由、Schema和Migration不变。

## 已证实的问题与未知项

### 本次成功可见反馈返修

2026-10-17，ca97在已有授权范围明确放行最小纯前端返修。沿a488正常追加，不改变原候选/旧包。
本轮依据为2026-10-16 HuanYu的既有一次成功：CID`5e3f475d-0ad5-49e7-a066-0f5077162cd8`，
上海23:27:35.866 Main refresh finish、Backend HTTP200 Request ID`ea198ff7-8c14-4cfa-a472-309b10f29085`，
原v6→VALID v7，validatedAt为`2026-10-16T15:27:34.958961Z`，租约已清。
该真实保存证据直接复用，不再要求登录或发平台请求；Stored v7的后续独立业务请求没有新增验证。

人类反馈未看到任何提示。源码成功后删除feedback，只保留App.vue默认top/3000ms短消息；
列表只显示前后均有效的状态，详情NAlert也因feedback删除无法回看。现有证据不能证明toast未触发、
被原生窗口遮挡或只是到期，不能把其中任一解释写成唯一根因。

在旧a488用合成成功及查询刷新失败验证局部结果确实不存在后，实施以下范围：

- 同店VALID/版本+1/有效validatedAt及scope通过后清active、保留非busy的本次success元数据和说明。
  仅格式化返回时间；保留原message.success/查询失败warning，不改全局Provider/duration。
- 列表在原96px状态格用原small StatusTag/NTooltip显示3字短结果与完整说明，原列宽/scroll-x/操作顺序/CSS不变；
  后续失效等原状态优先，详情使用原NAlert success/warning。没有新增行、布局或公共组件。
- 下一次登录/上下文/离页清除，不持久化或补播历史消息；再次点击原窗仍只focus，不重复保存。
  查询失败不抹掉权威保存结果，错误/不完整/跨scope结果不登记成功。原失败、取消、迟到和三次上限不变。

本次4文件66项定向通过（最终6.29s），lint/typecheck与Real build16.16s通过。
四主题用实际Token验证新旧Tag高度/字号CSS变量相等、状态格96及scroll-x1114不变、操作仍为查看/登录/启停/移除；
这是jsdom组件/尺寸契约，不是原生像素或用户视觉确认。测试CSS初次通过Vite空CSS stub取值失败，
已改为测试直接读取本仓tokens.css，不修改生产主题或放宽尺寸断言。
Backend/Electron/IPC/Schema/Shared/App.vue/包版本相对a488逐树无差异；不重跑未变Backend/Electron或重打包，
待ca97登记新前端与已核销a488/1.0.7壳的关联并复验。完整Gate2仍PARTIAL，MyCookLab原拒绝子分支仍UNKNOWN。

ca97已有生产与本机只读证据定位的是MyCookLab，不是历史HuanYu：2026-10-16上海21:25:13.826、
21:25:42.498两次refresh HTTP500/`SHOP_SESSION_PAYLOAD_INVALID`，耗时23/21ms。对应Request ID
`f159544c-7840-4bc1-a7bb-60bcb2247e56`、`6c35c1f6-51c5-49fb-a5d0-9577f6ab71ff`。
原当前Session仍旧VALID v1，并未保存这两次新候选。另一次健康检查502/`PLATFORM_REQUEST_FAILED`
不是AUTH_INVALID，不作为Cookie失效证据。

旧链路可直接复现：identified → refresh拒绝 → 轮询onError → fail → cancel → bridge.close。
同时Backend complete的finally释放租约，Main却仍保留identified候选。只删close会留下不可用的旧租约，
也不能把未保存的候选说成成功。前端一次测试修复前确实观察到close被调用；Main测试修复前仍为identified。
新增Backend三项分层测试修复前均因details为null失败，修复后通过。

历史错误只给同一错误码，不能确认是Base64/JSON/Schema、平台不符、目标身份不符或候选验证处理。
没有读取或导出真实载荷，也不推断某Cookie缺失、版本过旧或平台风控。Renderer CID与Backend Request ID
原先没有同一请求关联字段；已有记录仅按同店时间/顺序关联，不能补写成ID直接匹配。

## 修复行为

- Backend保留原HTTP500及`SHOP_SESSION_PAYLOAD_INVALID`，只追加固定`details.refresh_stage`。
  编码、JSON、Schema、平台、候选身份、候选验证及验证后目标变化分别表达；不序列化Pydantic输入或异常。
  原失败保留旧Session、finally释放租约、事务外验证及写前授权/CAS完全保留。
- Main刷新失败后清零捕获Buffer、清除候选身份，转failed，释放旧租约但保留原窗口；不自动捕获或重发。
  原始后端message/任意details不进入UI或诊断，只记录固定安全分类和真实HTTP状态。
- 用户根据提示再次点击原列表/详情固定的“登录”时，重新获取当前授权下的新租约及版本，以同attempt、店铺、平台、
  团队和原人员Session上下文重新open并置前同一窗口。旧lease、跨目标和不匹配上下文不能复用。
  每attempt最多3次refresh提交；相同被拒候选忽略capturedAt变化后不再提交，须先完成重新登录。
  指纹只在Main内存使用，成功、取消或关闭时清除，不落盘、不返回Renderer。
- 刷新失败的状态轮询仅观察Main failed/closed元数据，不触发平台、捕获或保存；自然关窗仍清忙态，
  提示不随轮询重复弹出。显式继续去重，迟到租约只释放自身，不覆盖下一轮lease；人员/团队/权限变化仍取消。
- 401人员失效、403与次数耗尽禁止新的验证，固定登录入口仍可尝试置前原窗，不绕过权限/上限；平台AUTH_INVALID与人员失效区分。网络/未知结果称“未确认”，
  不承诺已发出的请求可撤回。未通过的新候选不改变旧有效Session，成功只认同店、非缓存VALID、版本+1及验证时间。
- 新店Onboarding识别后自动关窗、已有店铺成功后留窗/置前、取消/退出/原30分钟期限、晚到结果保护保持。

## 兼容与部署

匹配Preload新增可选常量`refreshRecoverySupported: true`，status只增加可选`refreshFailure`，
不新增IPC通道。新Renderer面对旧1.0.6桥接仍走原安全清理，不假称支持同窗恢复、不盲重调open。
旧Backend无stage时只记录通用拒绝分类。完整新体验必须使本候选Renderer、Backend及1.0.7 Main/Preload匹配。

ca97已独占登记1.0.7；从干净已提交精确Candidate运行既有`pnpm run package:win`，
EXE/manifest/SHA256按Source SHA独立交付，不覆盖1.0.6。AppID、userData、Profile、CookieEncryption、
固定生产Origin、发行Fuse及禁DevTools均不变。服务器部署不能替代本机安装包更新；Owner不安装或启动客户端。

## 实际验证

| 命令及位置 | 结果与边界 |
| --- | --- |
| Backend `.venv/Scripts/python.exe -m pytest tests/test_shop_session_refresh_service.py tests/test_shop_session_auth_context.py tests/test_shop_session_health_service.py` | 复用原Owner及ca97独立27项PASS，Owner1.31s；相对48dd后端字节不变，本轮不重复执行；Fake仓储/Session与合成平台，不是PG |
| Frontend `pnpm lint`、`pnpm typecheck` | PASS |
| Frontend `pnpm exec vitest run src/features/shop-management/model/useShopLogin.spec.ts src/features/shop-management/model/management-login-poller.spec.ts src/features/shop-management/ui/ShopListTable.spec.ts src/features/shop-management/ui/ShopConnectionSection.spec.ts` | 返修4文件49项PASS，5.89s；含P1/P2新增回归、原桥接/无团队、同窗继续、新版本、双击、自然关闭、取消及迟到租约；旧39项历史通过不替代P1验证 |
| Frontend `pnpm build` | 返修Real production PASS，17.02s（首候选16.82s保留）；既有大chunk告警保留，不是Real平台或Electron验收 |
| Electron `pnpm typecheck`、`pnpm test` | PASS；最终67项，含Node合成Window/HTTP/平台适配器，覆盖同窗新lease、旧候选不重发、三次上限、目标/租约拒绝、头准备期间取消及安全诊断；没有原生Electron启动 |
| 受影响TS/Vue格式整理、`git diff --check` | PASS；锁文件、Shared、选品、Electron main窗口配置及Migration无差异 |

首候选最终格式检查初次指出useShopLogin.spec.ts格式差异，已仅机械整理并复跑；本次退回新增断言保持，不放宽。

Owner本轮未连接任何DB、未执行PG fixture/迁移、未启动服务/端口/第二Electron、未调用平台或生产refresh，
未读复制Profile/Cookie、未改变生产配置或共享stash。旧Feature库43仅retained，不借用Integration/生产；
本次无Schema变化且核心事务/仓储不改，现有Fake验证不冒称真实PG并发、实际Session或原生窗口通过。

## ca97 后续验收与恢复

1. 独立审查精确候选与匹配Source包，核对Main/Preload/status兼容及真实权限、版本/租约保护；
   如需DB/实际调用，按本轮明确分配处理，不对旧43库自动upgrade。
2. 在唯一匹配Real Electron中验证拒绝后原窗仍可操作、显式继续、关闭/取消、成功保存后留窗。
   实际MyCookLab拒绝子分支未知时，用安全stage查明后继续最小修正；不能把保窗或合成通过作为真实登录PASS。
3. 完成正常登录 → 权威验证 → 新Session版本保存 → 中控正式可用的证据，区分已有历史成功和本次新证据。
   失败时保留旧Session与安全分类，不在Owner侧重复生产请求。
4. Gate2与适用Release Gate通过后由ca97/Main继续，不带未批准清理；本Owner不合dev/main、不部署。
   回滚按正常revert/留存1.0.6安装器进行，保留Profile、Session及全部迁移，不清库、不降级。
