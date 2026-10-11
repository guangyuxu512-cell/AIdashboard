# Shop Login Session Sync V1 — Gate 1 / 2026-10-11

## 基线与边界

- Feature Owner：81a1；分支 `feat/shop-login-session-sync-v1`。
- 精确 Green 基线：`06992f4f3ee03e2ad689b25e7a4cb5837ce0d359`。Candidate 为包含本记录的提交，完整 SHA 以正式 Handoff 和桌面 manifest 为准。
- 用户直接授权来源：ca97 turn `01a12a36-e2c4-7092-9bb1-3a11c5674955`；旧选品恢复及后续五项体验成果已经包含，不重复改设计。
- 范围：既有店铺列表/详情登录、自动同步且成功留窗、候选验证与旧数据保护、显式单项每日 Session 失败恢复。
- 不改 Signer、平台算法、经营指标、每日09:00、选品界面或业务数据库结构；不扩展达人、自动登录、验证码、通用队列或新历史补采。
- Owner 不合并 dev/main，不使用 Integration 端口、不新开 Electron、不调用真实平台或操作生产。

## 改动及复用

| 层 | 现有能力及本次调整 |
|---|---|
| Frontend | 复用 AppButton、ShopListTable/DetailDrawer/ConnectionSection、Platform Registry、Shop/Session Query；页面级 `useShopLogin` 让列表与详情共用一条流程，动作顺序为查看/登录/启用或停用/移除。旧客户端明确提示安装更新。 |
| Electron | 复用 PlatformAuthAdapter、本机 persistent partition/Profile mapping、安全窄 IPC；新增 typed `focus-shop`，先按当前人员/团队复核权限，再置前 shop_id 唯一窗口。open/status/refresh single-flight，未完成尝试仍绑定原团队。 |
| Session | 复用加密 Accessor、HealthService、租约和版本CAS；短事务检查→事务外候选权威验证→重新权限/身份检查→短事务VALID保存及租约释放。失败候选不改变旧会话。 |
| 未配置 | 既有唯一 Shop 行插入 NOT_CONFIGURED 租约保留记录；内部版本1/加密空载荷不是有效会话，API隐藏占位时间，Accessor解密前拒绝。真实验证成功才版本2；新增店Onboarding仍版本1及原关闭行为。 |
| 有限恢复 | 复用正式retry API、Job唯一dedupe、全局领取锁/现有执行器；明确DAILY Session准备失败仅一次新尝试，原失败/累计次数保留，不改变普通更新和自动扫描。 |

已有店铺同步成功即清捕获Buffer/计时器/attempt和lease，浏览窗保留；再点击仅当前权限复核与focus，不捕获或保存。
用户关闭再开重新同步。首次新店仍按原Onboarding自动关闭。主窗口退出立即关闭所有相关窗口，不等待离线租约释放。

当前存储会话只在正式 `AUTH_INVALID` 时变invalid。网络、签名、未知业务拒绝显示“本次验证未完成”，不误清人员身份。
新候选AUTH_INVALID不证明旧Session失效；错店/取消/撤权/过期/CAS冲突及迟到响应均不得覆盖原有效快照。

## 数据库与API

Integrator登记专用 `control_center_feat_shop_login_session_sync`，最小应用角色 `control_center_dev_user`，
现有受保护35433连接；本地配置和辅助脚本ignored。实际单一Head `20261010_0043`、47表，**无新Migration/Schema/Slot**。
0042/0043不改写，旧选品库保留且不复用。测试后只读检查Shop、ShopSession、经营Job/Item均0，无真实Session或测试残留。

既有 `POST /api/v1/operating-dashboard/collections/{job_id}/retry` 的可选
`session_recovery_version` 必须与数据库当前新采集且新鲜VALID版本一致，Body恰好一个原Item。
原失败限定 `DAILY / FAILED / retryable / session_preparation / SHOP_SESSION_VALIDATION_FAILED`。
店铺权限/启用/抖店/真实身份/完整历史日/经营范围、完整事实及活动或较新失败去重均继续有效。
`dedupe_key=session-restored:{原ItemUUID}` 关联一次新执行；重放返回原Job，失败或超时成为non-retryable FAILED，
不会自动暂停续跑或因版本变化重置预算。普通retry请求不带该字段，原行为保持。

## 实际验证

所有平台响应、凭据和身份均为合成测试数据，以下不宣称真实平台或生产成功。

| 检查 | 实际命令/环境 | 结果 |
|---|---|---|
| 后端常规Gate | 在专用Feature配置下 `python -m compileall -q app`；`python -m pytest` | 604 passed、201 integration deselected；1项既有Starlette弃用警告。 |
| Session回归 | `python -m pytest tests/test_shop_session_refresh_service.py tests/test_shop_session_health_service.py -q` | 15 passed。候选失败保护、版本冲突、现有健康检查失效分类。 |
| 真实PostgreSQL | `python -m pytest tests/integration/test_postgresql_shop_login_sync.py -m integration -q`，上述独立库 | 37 passed。双连接保留行/租约、取消过期/撤权/身份/CAS、Set-Cookie、freshness299/300/301秒、跨进程恢复去重/一次领取/失败超时/迟到保护、成功0阻止补采。 |
| 前端 | `pnpm run lint`、`pnpm run test`、`pnpm run typecheck`、`pnpm run build` | lint/typecheck/Real production build PASS；141文件614 tests PASS。既有JSDOM离线XHR诊断与大chunk警告保留，不视为真实请求。 |
| Electron | bundled Node24 / `pnpm run test`（含clean/build/typecheck） | 27 passed。已有店同步留窗/清Buffer、关闭重开、跨团队同Shop只focus、未完成跨团队禁止复用、取消迟到/退出、首次新增回归、IPC白名单/原安全Origin与userData。 |
| Real浏览器契约 | `pnpm exec playwright test --config playwright.shop-login-real.config.ts`，4176 strictPort，所有API及桌面桥接完整拦截 | 2 passed。列表/详情版本刷新、重复focus零新租约/保存、AUTH_INVALID不清人员、普通成员无登录入口。**不是原生Electron证据**。 |
| 仓库 | `git diff --check`，ignored材料/改动范围检查 | PASS；不提交环境、Cookie/Token/签名、请求URL、日志、截图或二进制。 |

浏览器证据：`frontend/test-results/shop-login-sync-Real-list--80923-es-no-further-lease-or-save/real-contract-shop-login-detail.png`
（受忽略、本机合成正式契约），不替代唯一Integration Electron。

## 桌面交付、Gate 2及恢复

Electron版本1.0.4；保留App ID `com.siyu.controlcenter`、固定userData、生产HTTPS Origin、原Sandbox/IPC/Fuse，
无新依赖。必须从本Candidate的干净提交构建正式NSIS x64；EXE、manifest、SHA256SUMS按版本/候选单独保存在
`D:\中控台\dist\desktop\`，准确SourceSHA、路径及checksum由Handoff回传。服务器发布不会更新已安装Main/Preload。

ca97 Gate 2待验：唯一Real Electron打开已有VALID及未配置店、真实目标身份匹配自动保存、失效后人工登录、错店/取消保护、
成功留窗/再次focus、切团队/关闭重开/退出、状态与版本/时间刷新。不得用上述浏览器或合成PG代替真实登录。
Owner没有安装/升级或真实平台证据，生产缺口仍由ca97/Main在发布后用正式路径受控处理。
此前Main只读记录两店各三次DAILY Session准备失败；业务码100704原因未确定，不归为Cookie失效。
实际生产重登前再确认其他暂停/活动任务范围，限授权的两店2026-10-10，不扫描其他历史。

回滚：使用Gate2/Release前版本的服务器镜像和同App ID保留安装器，备份userData；无Schema降级，保留当前Session版本、
失败历史及恢复Job，不删除数据。若恢复执行已失败不可自动再次启动，须根据实际错误另行授权处理。
Gate1技术检查不表示Gate2、CI、Release或生产恢复已完成。
