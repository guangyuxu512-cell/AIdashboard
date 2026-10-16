# 店铺身份来源与错店纠正 Gate 1

Owner 为 81a1，独立审查交 ca97。源码修复及 998 合前 Gate 2 已完成；现按新增人类授权准备 1.0.8 匹配交付，Owner 只制作并交接包，安装、合并和发布由后续责任人执行。

## 集成验收与正式交付授权

ca97 已独立验证 998 全 83 项 Node、前端 61 项、lint/typecheck/Real build 及实际 Service 身份边界，真实网络/Profile 访问哨兵为零。匹配 998 的唯一 Real Integration Electron 随后完成三轮受控真实专项：前置正常保存 valid v8、错店拒绝且旧 v8/绑定保留并留窗、原失败窗口切回后显式新 lease 继续保存 valid v9。原任务事实摘要保持，三次 refresh 预算已用尽，不重复登录。

规划人类 turn `01a146fd-f4c5-7383-af58-d41e0b5c9f3b` 对紧邻完整交付范围直接“同意”，ca97 已独占登记 1.0.8。此后仅从 998 正常追加 `electron/package.json` 版本、`electron/docs/05-打包升级与验证.md` 及本记录三路径，形成新的精确 Source；所有运行、Frontend、Backend blob 均保持 998，不混入 98 反馈、PDD 新逻辑、布局、商品数据或清理。

交付提交须干净，现有 `package:win` 自动完成 TypeScript/83 Node、NSIS、Fuse、PE、hash 与 manifest 生成。安装器名、manifest 和 ASAR 的 Source 必须为实际交付提交，不手填为 998；EXE、manifest、checksum 保存在按版本与 Source 分开的新目录。该次实际 SHA/size/hash/包验证结果随正式 Handoff 和生成 manifest 提交审查，不在源码文档中预填尚未生成的值。

Owner 不操作 Integration/生产、Profile、窗口或平台。ca97 独立核包后走 dev 合并复验及精确 CI，Main 再按 Release Gate 部署配套 Renderer；生产健康后才正常退出开发窗口、保留 userData 覆盖安装。新鲜安全检查后的生产 MyCookLab 一次正常登录由规划统一通知，失败即停，无自动重试。授权不等于已安装或已部署。

## 恢复身份 IPC 边界返修

ca97 对 `bc4bdc80c6bb28d7a358233ec34ad7904042b00b` 的独立审查发现：已有店铺首次 identified 时，Backend 验证前的捕获店铺身份已经由状态 IPC 返回。新 UI 没显示该值，不能替代 IPC 边界保护。此为合成 Service 证据，不是生产泄漏证据，也不解释历史单次失败的唯一根因。

本次仅正常追加四路径：`management-login-service.ts`、原 `management-login-sync.test.ts`、原 IPC 契约及本记录。状态序列化依据永久 `recoveryShopId` 对已有店铺始终返回 `identity=null`，不依赖会被释放清空的 `recovery`。内部身份和捕获 payload 不变，仍用于既有验证和正确恢复；首次新增仍返回识别身份并自动关闭。

原候选加入回归后，定向四项为 2 PASS / 2 FAIL，两个恢复身份外传断言失败，Onboarding 正对照通过。修复后 Electron typecheck、clean TypeScript build 和全 83 项 Node 测试通过；原同一用例还覆盖 lease 清空的实际序列化器、失败后状态、同候选拒绝、显式新候选成功及提交 payload 保留。格式与 diff 检查通过。

Frontend、Preload、类型、Backend、数据库、包版本及其它源码相对 bc4 均无差异，复用未变的前端 61 项、lint/typecheck/Real build 记录，不重复浏览器或原生检查。本次仍无真实平台、DB、Profile、窗口、服务、打包、安装或生产操作；新精确 Candidate 交 ca97 重新独立审查，不以旧 83/61 通过代替边界修复验收。

## 基线与范围

- 分支 `feat/shop-login-identity-source-v1`，直接基线为精确 Green `e4b70a272b0327efb5d5aa0768811d6315dd123d`，CI 38941889261 三项成功。
- 基线运行代码与已发布 `c085a3f75a84f9ac68ea9da7473782431de252a3` 一致。原诊断 229d5c6、恢复 a488、反馈 98c1330 及各分支、包和本机材料保留。
- 从 a488 逐路径复用必要留窗与人工继续代码，不合并整条恢复分支，不引入 98 的成功反馈、successMap 或查询刷新修补。
- 源码修复共 10 个运行路径、8 个定向测试路径、3 份现有契约及本 Gate 1 记录；交付增量再增加 package 版本和发行文档，共 24 路径。除显式版本元数据外，Backend、Shared、CSS、选品、窗口框架、依赖、Schema 和迁移不变。

## 身份与恢复行为

抖店仅使用现有 `shop_info_v2` 的明确 `data.shop_id/shop_name`。HTTP 和业务状态须合法，data 不接受数组；ID 接受非空字符串或正安全整数，保留长字符串，不将不安全数字舍入。账户字段、任意递归同名字段和数组首项均不组成店铺身份。四条无明确身份契约的 fallback 取身份请求撤下，原 probeIndex 0 与固定观察边界保留。

已有店铺候选刷新被拒时，Main 清零 payload、释放旧 lease、保留原窗口和原 Session。仅 `candidate_identity` 或 `PLATFORM_IDENTITY_MISMATCH` 产生 `identity_mismatch`；Schema、网络、人员认证、平台认证、权限、版本及未知错误保留独立分类。错误文本不反射平台或 Backend 原始 message/body。

固定“登录”入口允许用户在原窗口手动切换正确账号后显式继续。每次重新获取当前权限下的新 lease 和 expected version；同目标、同 attempt、同人员浏览器 Session 才可重新捕获。相同被拒候选不再 POST，每次 attempt 至多三个显式 POST；不自动清 Cookie/Profile、改绑定、复用旧 lease 或自动重试。达到上限或权限阻止后，登录只做授权置前，仍可取消。

失败状态轮询只读 Main 状态，不额外访问平台。原窗口在续租中、续租失败或超时后仍可观察关闭；迟到 lease 独立释放，迟到捕获只清零，取消和上下文变化不能复活旧操作。首次新增自动关闭、其它平台身份方式、原成功留窗及服务器 CAS 校验保留。

## 界面与契约

列表只在原 96px 登录状态格使用既有 small StatusTag 与 Tooltip 显示“店铺不符”。提示明确说明本次失败、原登录状态保留；目标名仅来自当前已授权 Shop ViewModel，不显示候选他店身份，不修改数据库 VALID 状态。原列宽、操作顺序、固定登录入口和 scroll-x 不变。

详情复用原 NAlert；查询加载或失败时仅保留当前 typed 错店提示，真实 Loading/ErrorState 和重试继续显示，不将旧缓存当成新结果。普通读取错误不显示错店提示。取消、自然关闭、成功、人员/团队/权限变化清除本次反馈；不持久化或历史重播。

Preload 增加固定可选 `refreshRecoverySupported: true`；原状态类型增加可选 `refreshFailure`，Main 与 Renderer 类型同步。没有新增 IPC 通道或通用执行能力。旧桥接仍安全清理，不假装具备恢复能力。

## 文件清单

| 组别 | 文件 |
| --- | --- |
| Electron 运行 5 | services/douyin-platform-auth-adapter.ts、services/management-login-service.ts、services/login-diagnostics.ts、preload/index.ts、types/desktop-api.ts |
| Frontend 运行 5 | types/desktop.d.ts；features/shop-management/model/useShopLogin.ts、management-login-poller.ts；ui/ShopListTable.vue、ShopConnectionSection.vue |
| Electron 测试 4 | douyin-login-probe-observation.test.ts、management-login-sync.test.ts、desktop-api.test.ts、login-diagnostics.test.ts |
| Frontend 测试 4 | useShopLogin.spec.ts、management-login-poller.spec.ts、ShopListTable.spec.ts、ShopConnectionSection.spec.ts |
| 现有契约 3 | electron/docs/01-Electron边界与架构.md、02-IPC契约.md；frontend/docs/05-数据模型与接口契约.md |

## 验证

以下为 Owner 源码阶段的合成验证，未连接真实平台或业务数据库；ca97 的三轮真实集成证据另见前述交付授权及 Gate 2 记录。

| 命令与范围 | 实际结果 |
| --- | --- |
| 原身份解析器对新增 NodeVM 契约用例 | 2 PASS / 11 FAIL，证明递归账户字段等独立缺陷；修复后该文件 13 PASS |
| `pnpm --filter @control-center/electron test` 对应 electron 目录 `pnpm test` | TypeScript clean build 与全部 Node 测试通过，83 PASS；无原生 Electron 启动 |
| Frontend `pnpm exec vitest run` 四份上述定向文件 | 61 PASS，最终 6.11 秒；含错店保留/清除、状态格、续租与迟到保护 |
| 详情加载与读取错误错店提示回归 | 修复前两项 FAIL 已复现；修复后含非错店对照和反馈清除均通过，正常分支仅一份提示 |
| Frontend `pnpm lint`、`pnpm typecheck`、`pnpm build` | 全部通过；生产 Real build 15.67 秒，保留既有大 chunk 警告 |
| Electron `pnpm typecheck` 与最终文件检查 | 通过；diff --check 通过，实际 22 路径与白名单一致；两个 Vue style 逐字不变，Backend/Shared/选品/窗口/依赖/包版本无 diff，本地覆盖及构建产物保持 ignored |

首次 Frontend 测试命令误将 `--` 透传，导致未按文件过滤；已中止，不计入通过结果，随后用 `pnpm exec vitest run 文件路径` 完成上述定向验证。没有为重跑而放宽断言或修改无关模块。

## 证据边界与下一步

既有生产单次失败已定位在 `candidate_identity`，发生于权威候选校验/保存之前，原 Session 保留。旧解析器缺陷可用原函数与合成结构复现；该次实际候选的字段来源未保留，不能认定用户登错账号或此缺陷就是唯一根因。

Owner 的数据库、真实平台、生产登录、原生窗口、服务启停、Profile 读取及安装动作均为零。未重复验证已通过的选品 A/B，也未操作当前 Integration/生产配置。Backend 已发布诊断保持不变，无 Migration，无 Feature DB 需求。

本候选修改 Main、Preload 和 Adapter，真实验收和正式客户端必须匹配精确 Source；仅部署服务器 Frontend 不能更新旧客户端。1.0.8 已获完整交付授权，当前版本元数据追加不改变 998 的运行代码；旧 1.0.7 包完整保留，不作为本次交付包。

998 的功能合前 Gate 2 与真实集成专项通过，不等于新交付提交已 Green、已安装或已部署。ca97 接收精确版本提交与包后继续独立核验，再推进合并和发布。应用回退须成套匹配 Renderer/Preload/Main，保留现有 Profile、Session、Schema 与所有历史证据；不通过清理用户数据回退。
