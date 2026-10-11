# 店铺登录状态同步 Gate 2 与发布交接

2026-10-11，Integrator ca97，Feature Owner 81a1，Main 承接 Release Gate、服务器发布和匹配客户端交付。
Gate 2 审查、集成验证及合并后复验通过；精确 dev 推送并通过 CI 后才作为 Green 交接。
本轮只收口登录入口、Session 自动同步留窗、验证失败分类及受限的单项 Session 失败恢复。
不改选品界面、Signer、经营指标、每日 09:00 配置、依赖或 Migration，不追加达人等后续模块。

## 候选与合并

- Candidate：`9fc6409c015bec767a5d4a72304a5bb0c0d9e855`，远端分支 `feat/shop-login-session-sync-v1` 一致。
- Green 基线：`06992f4f3ee03e2ad689b25e7a4cb5837ce0d359`；Gate 1 见同目录 `shop-login-session-sync-v1-gate1-20261011.md`。
- Gate 2A：ACCEPT。正常 `--no-ff` Merge：`62cc491cb023a2e1b5827d03a7923f370e6711a4`，两父提交分别为上述基线和 Candidate。
- 合并后的 Backend、Frontend、Electron 与 Candidate 相同。后续收尾提交仅工程记录，最终 Green SHA 以成功 CI 的精确推送提交为准。
- 单一 Head 保持 `20261010_0043`，相对基线 Migration 差异为 0；无新 Schema、无 Migration Slot，也未执行降级或重建数据库。

## 审查边界

列表与详情复用 `useShopLogin`、既有平台 Adapter、Session 查询和 typed IPC；列表顺序为查看、登录、启用或停用、移除。
登录入口不以 Session 已失效为前提，权限沿用既有规则。旧桌面桥接不能完成新流程时明确提示更新客户端。

候选 Session 在事务外做权威平台验证，再在短事务中复核权限、目标身份、租约和版本，原子保存 VALID 并释放租约。
取消、错店、撤权、CAS 冲突和候选验证失败保留旧快照。未配置店的租约保留行不是可用 Session，API 不显示占位时间，Accessor 解密前拒绝。
只有当前存储会话的明确 `AUTH_INVALID` 才变为 invalid；网络、签名和未知平台拒绝表示“本次验证未完成”，不伪报本次成功、不撤销人员登录。

已有店铺保存成功后清理捕获 Buffer、计时器与恢复 attempt，保留浏览窗。已打开的同 shop_id 窗口在当前权限复核后只置前，不重复捕获或保存；关闭再开重新同步。
未完成的尝试仍绑定原团队，不能跨团队复用。首次添加店铺的成功自动关闭行为保留。

有限恢复仍用 `POST /api/v1/operating-dashboard/collections/{job_id}/retry`，可选 `session_recovery_version` 只接受一个原 Item。
原 Item 必须为 DAILY、FAILED、retryable、`session_preparation / SHOP_SESSION_VALIDATION_FAILED`；新鲜 VALID 版本、启用、授权、历史日、完整事实和活动任务检查仍有效。
`session-restored:{原ItemUUID}` 唯一键至多产生一次新执行，原失败和累计次数不改；重放返回既有 Job，恢复失败或超时不自动再试。普通重试、冷却和每日扫描不放宽。

## 真实 Integration Electron 证据

唯一开发主窗口“电商 AI 中控台”，Real `5180 → 8100 → control_center_integration`，Vite strictPort。
Main/Preload、前后端来自经过核验的精确 Candidate 快照，实际 API Schema 和前端登录 hook 已核对；合并业务树与该快照一致。
复用 `g2_sa_v1_super` 正常有效会话，服务端账号启用且为超级账号，真实管理读取返回 200；未改密码、权限或注入 Token。

Integration HuanYu：Shop `c448f225-b141-409b-bc94-12f1ae74ee04`，平台身份 `243321624`。
生产与集成 Shop UUID 不同，不把集成 Session 搬到生产。

| 实际操作 | 后端与原生窗口证据 |
| --- | --- |
| 在原历史 VALID v1 下点击登录，用户完成正常平台登录 | 自动保存 v2 VALID；上海时间采集 19:54:44.176、验证 19:54:45.381659，refresh 200、lease 201，租约已释放；Shop ID 和平台身份保留 |
| 成功后继续浏览 | 原生 accessibility 可见 HuanYu 的罗盘浏览窗与页面导航；保存计数仍为 1，版本和时间未变，未重复捕获保存 |
| 同店再次点击登录 | 保持一个店铺浏览窗，refresh/lease 计数各仍为 1，v2 和时间未变；置前效果未取得独立原生截图，不用网页截图代替 |
| 用户关闭店铺浏览窗后重开登录，回复“好了” | 自动保存 v3 VALID；上海时间采集 20:09:31.360、验证 20:09:32.535323；refresh 共 2 次均 200、lease 共 2 次均 201，租约已释放；罗盘浏览窗继续保留 |
| 无额外历史任务 | HuanYu 操作前后均为 10 Job、154 Item、0 active，登录同步未新增经营 Job 或 Item；Integration 采集、每日及选品执行开关为关闭 |

自动原生截图超时、点击坐标几何不可用；用户完成必要的正常认证和点击，后台回读与受支持的原生 accessibility 分别记录。
真实取消、错店、跨团队负向操作和 PDD 首次添加未全部重复人工平台操作，以下合成测试覆盖不得改写为原生实测。
匹配正式安装包的实际安装和生产登录仍属于 Main 发布后客户端验收，不能只部署服务器即宣告完成。

## 技术验证

| 检查 | ca97 实际结果及证据范围 |
| --- | --- |
| 精确候选 Backend 完整常规测试 | 604 PASS，203 integration deselected；与 Owner 记录的 201 deselected 分开，按 ca97 实际收集为准 |
| PostgreSQL 定向 | Integration 37 PASS；真实 PostgreSQL、合成平台，覆盖候选保护、双连接租约/CAS、取消撤权、freshness 299/300/301 秒、恢复一次性去重/领取、失败超时及真实零值阻止补采；合并后同组再次 37 PASS |
| Backend Session 回归 | 合并后 refresh/health 两文件 15 PASS |
| 精确候选 Frontend 完整 | lint、typecheck、Real production build PASS；141 文件、614 unit PASS |
| 合并后 Frontend | lint、typecheck、登录 hook 8 unit、Real production build 全部 PASS |
| Electron | 精确候选和合并后 build/typecheck/unit 各 27 PASS；负向生命周期、身份保护及首次添加兼容属于合成测试覆盖 |
| Real 浏览器契约 | 既有 5180 上 2 PASS，HTTP 与桌面桥接完整拦截；不是原生登录或真实平台证据 |
| Hygiene | `git diff --check` PASS，敏感 tracked 文件 0、凭据 literal 匹配 0；环境、日志、截图、PID、脚本、二进制与本机覆盖 ignored |

PostgreSQL 本轮专用夹具残留为 0；现有账号、HuanYu Session、经营事实和历史任务保留。
首次 Electron 测试曾遇依赖下载未结束的 Windows 目录创建冲突；确认完整既定 Electron 44.3.0 文件后重跑通过，未改依赖、锁文件或构建校验。
正式 NSIS 原始 checksum 核验通过，不以本地测试替代精确 dev、main CI。

## 资源与桌面交付

Feature DB `control_center_feat_shop_login_session_sync` retained，Owner `control_center_dev_user`，单一 0043、47 表；角色无 CREATEDB、CREATEROLE、SUPERUSER。
Feature `8101 / 4176 --strictPort`，Integration `8100 / 5180 --strictPort`；受保护 35433 隧道和专用 SCRAM 规则保留，不改其他库或生产存储。

匹配桌面版本 1.0.4、Source SHA 为 Candidate，产物：
`D:\中控台\dist\desktop\1.0.4-9fc6409c015b\Siyu-AI-Control-Center-1.0.4-9fc6409c015b-windows-x64-setup.exe`。
大小 120304140 bytes，SHA-256 `4793a6947dc73f1cc1f2e628b7938fb293991a86780fe679cbd15624a29c6860`，同目录 manifest、SHA256SUMS 已交付并由 ca97 独立复核。
保留 App ID、userData、生产 HTTPS Origin、Sandbox 与 Fuse；未新增签名或自动更新。服务器发布不会升级已安装 Main/Preload，必须完成匹配客户端手动升级并核验实际版本。

## Main 发布与受控补采

Main 已提供只读基线：生产 `5f235433660e18eaa82289ef14c2cb3ce1caf92b`、`control_center_prod`、单一 0043，服务健康。
2026-10-11 17:20:25 上海时间的 HuanYu 同 Session v1 身份诊断为上游 HTTP 200、整数 st=100704，Backend `502 / PLATFORM_REQUEST_FAILED`；该身份接口不经过 Signer。
100704 的认证含义未证实，也不能作为 09:00 历史失败的具体上游码。不得凭历史 VALID 或未知拒绝宣称当前 Session 可用或已失效。

授权恢复范围只限 2026-10-10：

| 店铺 | 生产 Shop ID | 原失败 Item |
| --- | --- | --- |
| HuanYu | `66a0ccc6-88cb-44bb-9c4c-f4a43fe07698` | `a6a43ad8-5267-4759-b335-50ca635d3956` |
| MyCookLab | `fc56c300-2f72-4e21-aedf-ee5778c9309f` | `d33496e0-8c5f-4c16-b7dd-a8a3ebd3c5cc` |

原 DAILY Job `c91d78da-dcc1-409a-be0c-c4dd7ae5f930`，两项均 Session 准备失败、累计 3 次，尚无该日事实；指标请求前失败，历史上游响应未记录。
海洋同日已成功 3492 分、7 单、2 退款单，必须保留且不重采。
18:12:01 的只读快照显示两店无其他 PAUSED/PENDING/RUNNING、无范围外活动项；这是当时快照，生产登录前必须重新核查，防止既有恢复语义启动未授权任务。

Main 取得精确 Green CI 后完成 Release Gate、main 完整差异、生产预检和可读备份，正常合入并等待 main CI 与单次正式 Deploy。
实际服务器 SHA、服务健康、单一 0043、Real UI 和匹配 1.0.4 客户端核验后，用户在生产正常登录目标店铺；不得复制集成 Cookie 或直接改库状态。
只有新采集 VALID Session 满足现有 300 秒 freshness 和其他约束，才对上述原 Item 逐项走正式 session recovery retry。
恢复结果、指标入库/API/页面与完整数据普通更新跳过分别核对；未知值不填零，失败不自动重复，原历史不删除，原每日 Asia/Shanghai 09:00 和执行开关保持。

共享 Git 失败使用正常 revert。无 Schema 降级或清表，应用回退保留 Session 版本、审计和恢复 Job，桌面回退使用同 App ID 已留存安装器并先备份 userData。
Gate 2、CI、部署成功各自记录；只有生产服务器、实际客户端及对应业务核验完成后才标记 DEPLOYED。
