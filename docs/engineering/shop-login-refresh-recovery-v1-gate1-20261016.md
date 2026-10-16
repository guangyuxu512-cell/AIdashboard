# 店铺登录刷新拒绝与人工继续 Gate 1

2026-10-16，81a1 → ca97。本候选修复刷新失败后提前关窗和失效租约无法继续的问题，
增加安全的拒绝分层；MyCookLab实际载荷拒绝子分支仍待匹配版本取证，不能据此宣称真实登录已恢复。

## 基线与范围

已直接回读规划人类`01a14500-90c2-7b42-8a11-5ccba24ee1a6`及上下文。ca97明确批准从已发布
功能Green`1773a97d27c56512a620337e3259cceabadca2f1`建立`feat/shop-login-refresh-recovery-v1`。
该基线精确CI38789232361三Job成功；不混尚未批准发布的清理1aec/Green5a18或7d55。
精确Candidate、clean/push回执及匹配Source包以本次正式Handoff/manifest为准。

只改既有Session refresh校验分层、Main/Preload/status契约、原列表/详情登录反馈及定向测试。
沿用ShopSession、原租约、权威验证、CAS、Profile映射、窄IPC及既有轮询；无新登录系统/队列/框架。
选品A/B、已确认界面、Connector/Signer、经营恢复、权限/API路由、Schema和Migration不变。

## 已证实的问题与未知项

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
- 用户点击原列表/详情的“继续登录”时，重新获取当前授权下的新租约及版本，以同attempt、店铺、平台、
  团队和原人员Session上下文重新open并置前同一窗口。旧lease、跨目标和不匹配上下文不能复用。
  每attempt最多3次refresh提交；相同被拒候选忽略capturedAt变化后不再提交，须先完成重新登录。
  指纹只在Main内存使用，成功、取消或关闭时清除，不落盘、不返回Renderer。
- 刷新失败的状态轮询仅观察Main failed/closed元数据，不触发平台、捕获或保存；自然关窗仍清忙态，
  提示不随轮询重复弹出。显式继续去重，迟到租约只释放自身，不覆盖下一轮lease；人员/团队/权限变化仍取消。
- 401人员失效、403与次数耗尽禁止继续；平台AUTH_INVALID与人员失效区分。网络/未知结果称“未确认”，
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
| Backend `.venv/Scripts/python.exe -m pytest tests/test_shop_session_refresh_service.py tests/test_shop_session_auth_context.py tests/test_shop_session_health_service.py` | 27项PASS，1.31s；Fake仓储/Session与合成平台，覆盖拒绝分层、旧值保护、新租约纠正后保存、目标变化、原健康与Accessor契约 |
| Frontend `pnpm lint`、`pnpm typecheck` | PASS |
| Frontend `pnpm exec vitest run src/features/shop-management/model/useShopLogin.spec.ts src/features/shop-management/model/management-login-poller.spec.ts src/features/shop-management/ui/ShopListTable.spec.ts` | 3文件39项PASS，最终6.36s；原桥接/无团队、同窗继续、新版本、双击、失败不自动重发、自然关闭、取消迟到租约、原成功反馈及按钮行为 |
| Frontend `pnpm build` | Real production PASS，16.82s；既有大chunk告警保留，不是Real平台或Electron验收 |
| Electron `pnpm typecheck`、`pnpm test` | PASS；最终67项，含Node合成Window/HTTP/平台适配器，覆盖同窗新lease、旧候选不重发、三次上限、目标/租约拒绝、头准备期间取消及安全诊断；没有原生Electron启动 |
| 受影响TS/Vue格式整理、`git diff --check` | PASS；锁文件、Shared、选品、Electron main窗口配置及Migration无差异 |

最终格式检查初次指出useShopLogin.spec.ts格式差异，已仅机械整理该文件，并重新跑39项通过；未放宽断言。

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
