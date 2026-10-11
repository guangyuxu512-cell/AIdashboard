# AGENTS.md

## 0. 工程工作流总则（Two-Gate）

本文件同时是仓库工程治理的最高规则；模块 `AGENTS.md` 只保留各自的技术边界，并引用本节。完整操作流程、环境登记与数据库协作细则见：

- `docs/engineering/01-开发集成与发布流程.md`
- `docs/engineering/02-工程环境与工作树登记表.md`
- `docs/engineering/03-数据库与Migration协作规范.md`

### Branch 与 Worktree 角色

- `main` 仅保存已发布或已确认稳定的版本；只能由通过 Release Gate 的 Green `dev` 合入。
- `dev` 是唯一集成线，也是 Green `dev` 的唯一来源；Feature 只能通过 Integration Worktree 按 `--no-ff` 合入。
- 新业务在 `feat/*`，紧急线上修复在 `hotfix/*`；不得建立长期 `qa/*`、`test/*`、`review/*` 等平行集成线。
- 新 Feature 从最新 Green `dev` 创建，且一个 Worktree 只绑定一个分支。已有 AI、Mobile 长期分支按登记表保留，不因本规则补做 rebase、重建或改名。
- 当前工作树中的 `AGENTS.md` 和 `docs/` 才是该分支的规则快照；禁止把其他 Worktree 的文件当作当前分支事实。

### Two-Gate、问题归属与共享历史

2026-10-11 当前81a1任务：从精确Green
`06992f4f3ee03e2ad689b25e7a4cb5837ce0d359` 接续
`feat/shop-login-session-sync-v1`。仅完成店铺列表/详情共用登录入口、目标店铺身份核验、
候选Session权威验证后原子保存、成功后结束捕获但保留浏览窗口，以及显式单项每日Session失败恢复。
支持平台和管理权限沿用既有规则；valid亦可登录。首次新店Onboarding仍成功保存后自动关闭。
失败候选不覆盖原Session；不将网络、签名或未确定平台错误标为认证失效。
Integrator已分配专用空库 `control_center_feat_shop_login_session_sync`，Owner
`control_center_dev_user`，仅本地受保护凭据经35433访问，Feature端口8101/4176 strictPort。
只升级既有迁移至单一 `20261010_0043`；无新Schema/Migration、Slot FREE，不使用旧选品库。
恢复复用既有retry API/队列/锁和Job唯一键，只覆盖原DAILY的明确Session准备失败，
新鲜VALID版本通过权限/启用/去重检查后至多一次；保留原失败和累计次数，普通重试上限不变。
Owner只完成Gate 1与匹配Source SHA的正式桌面包交ca97；真实登录/生产恢复由ca97/Main协调。
禁止Owner写Integration/生产、合dev/main或发布。旧选品界面恢复已完成，不再重复审核或改设计。

2026-10-11 新一轮选品体验收口：81a1 从精确 Green
`a9931a8f8b329bb5e5e79f9e44fd42294ca5d633` 创建
`feat/product-selection-experience-fixes-v1`，保留原策略列表/抽屉和手动接入。
仅收口本次主动获取的消失消息、视频区间格式、差评率百分比、24小时店铺类目缓存与弹层边界。
复用 retained `control_center_feat_product_selection`（单一0043）、Feature 8101/4176；无新Schema或Migration。
0042/0043、Session/Signer、日期规则、事实与权限不改；不新增策略保存、调度、百应或手机能力。
Gate 1候选 `6e6bfc63f8ee5f3155c134fcb527f44eb9bf4508` 已经ca97整体审查并no-ff合入
`5eababba8b0c466f65ad0ec437a1b66e39d96b90`，同一Integration的5180/8100实际加载该候选。
技术与真实读取验证通过，按用户本轮指定继续dev精确CI及Main交接；旧41e预览不作为本轮证据。
原生普通/最大化菜单尺寸人工确认未单独取得，明确交Release Gate核对，不以浏览器拦截替代。
开发会话不合并dev/main、不发布；详细范围和证据见
`docs/engineering/product-selection-experience-fixes-v1-gate2-20261011.md`。

当前状态（2026-10-11）：选品手动Candidate `41e3116e0e176761f3a3fbb29e199283ce61c95c`
通过Gate2，no-ff Merge `3448b7d74651bcaab3f39dbeff97aee9a5fcea83`；Integration单一0043。
HuanYu正式run `72f42fff-1996-4d59-9c30-30104f373e63` 真实10条入库及10条basic_info成功，
用户确认Real列表/详情/刷新。此run首选10-04～10-10成功、未触发备用；窄621000704第一页补查有PG覆盖，
不把该业务码普遍解释为日期未就绪。0042/0043 Slot统一released，Feature库retained，失败历史保留。
下列旧UI_ONLY/PARTIAL为阶段记录；当前手动闭环与CI/Release边界见
`docs/engineering/product-selection-manual-v1-gate2-20261011.md`。未生产核验前不标记DEPLOYED。
达人登录、策略保存、定时、手机及百应仍未接入，不能假成功。

本期 Feature 登记（2026-10-08）：81a1 `feat/product-selection-frontend-v1` 从 ca97 确认的 Green
`b34e43cb90356e03d2f793c4146c6775a11f5ab3` 开发选品库前端与 Mock 交互，状态 `UI_ONLY`。
复用 framed 导航、既有列表/分页/Drawer/表单/ShopSelector/主题；采集任务与商品库仍占位。
typed service 为前端草案，Real 不请求猜测接口、不回退 Mock。无 Backend、Schema、Migration、Worker、
真实平台、真实调度或达人登录/Session 保存。Gate 1 后交“集成ca97”唯一 Integration Electron 验证 Mock
与 Real 边界；Green 后交原发布会话，开发会话不发布。旧分支、提交与本机忽略材料保留。

2026-10-09 用户授权按两个阶段接续本 Feature：先完成紧凑候选列表、详情首屏和说明精简的前端返修，
仍为 UI_ONLY，无新增业务数据库/Migration；由 ca97 加载精确新候选进行集中页面复验。
前端确认后才实施罗盘手动选品最小闭环（条件→榜单请求→候选持久化→basic_info补充→正式查询）。
该阶段复用ShopSession/HTTP/Signer/商品模块授权与团队隔离；必要Feature DB与Migration Slot由ca97分配。
不扩展百应、达人登录、每小时监控、手机任务或自动上架；开发会话不操作main/生产，Mock不能替代真实闭环证据。

选品接入资源登记（2026-10-10）：81a1 沿用 `feat/product-selection-frontend-v1`，基线
`b34e43cb90356e03d2f793c4146c6775a11f5ab3`。前端候选 `06bd03c0fa61b00251063e21350cd0cc5445afe5`
及诊断补丁 `819ca33ba6548030e418320c6bb80ba046beb842` 尚未合入 dev；Frontend/Electron 树相同，
Mock 验证不代表真实入库。两表、业务专用 `product_selection_runs`、观察的可空 `last_run_id`
及 Real 查询已在阶段候选实现；技术复核通过但仍为 PARTIAL，空榜单、失败和中断有独立记录，
不增加通用队列、Worker、策略调度或自动平台重试。具体事务/幂等约束见选品资源登记文档。
0041 已在 Integration/生产应用，旧 Slot released；本 Feature 保持唯一 active Slot，串行链为
`20260924_0041 → 20261010_0042 → 20261010_0043`。0042 已在 Feature 库应用，不改写、不释放；
追加 `20261010_0043_product_selection_runs_v1`，revision `20261010_0043`，down `20261010_0042`，
由 81a1 编写且已在 Feature 库应用；两项随同一完整候选验收后一起释放，不另开第二个活跃 Slot。
独立库 `control_center_feat_product_selection` 现为单一 `20261010_0043`，ShopSession=0，Owner `control_center_dev_user`，
受信任 `35433` 隧道及 SCRAM 连接/回滚 DDL 探针通过；应用角色无 CREATEDB/CREATEROLE/SUPERUSER。
81a1 本地忽略连接及实际库名已核验；保持现有库和0042事实，未知渠道/日期/类目转换不猜测实现。
Feature Backend `8101`、Frontend `4176 --strictPort`，仅 Feature Owner 运行；Integration 仍为
`8100/5180 --strictPort` 与唯一 Electron。仅登记/评审，不代 Feature 写 Migration，不发布生产。

- Gate 1 由 Feature Owner 完成：自检、测试、文档/契约同步、提交，并以正式 Handoff 交给 Integrator。
- Gate 2 只在 Integration Worktree 执行：读取候选提交、做集成验证、解决真实冲突并决定接受或拒绝。候选本身的业务 Bug、缺测试或契约缺口必须退回原 Feature Owner；Integrator 不代为开发业务修复。
- Gate 2 通过后只允许 `git merge --no-ff feat/*` 合入 `dev`。集成后 `dev` 失败时，应拒绝候选或在共享历史上 `git revert`，禁止 `reset`、改写历史、未审查的 rebase/cherry-pick。
- Release Gate 要求 Green `dev`、验证证据和发布说明完整；未经该 Gate 不得合入 `main`。

### 数据库、运行环境与本地材料

- Schema 变化由 Feature Owner 编写 Alembic Migration；同一时刻只能有一个登记的 Migration Slot。Integrator 负责分配 Slot、验证候选，不替代 Feature 编写新 Migration。
- Feature 使用自己的可重建临时/Feature 数据库；Integration 只写 `control_center_integration`；Main smoke 只写 `control_center_dev`；未来生产环境必须独立。不得混用或把凭据写入 Git。
- 固定运行隔离：Main `8000/5173`、Integration `8100/5180`、AI 前端 `5174`、SSH Tunnel `35433`。Vite 必须显式端口并启用 `--strictPort`。Mobile 端口以当前 `mobile` 配置为准，不能因历史记录把 `5175` 视为永久保留端口。Integration Electron 如需联调只指向 `5180`，且不启动第二个 Electron。
- `.dev-runtime/` 是 Main 偏置运行管理器，记录的 PID 必须结合真实进程校验，过期记录不是唯一事实。临时脚本、日志、截图、build/test artifact、PID 与本机密钥必须清理或被 Git 忽略，并在 Gate 1、Gate 2 检查。
- `AGENTS.override.md` 仅可作为 Worktree 本地覆盖文件，必须通过该 Worktree 的 `.codex/git-exclude` 忽略，禁止提交。版本化临时文档目录规则由 `.gitignore` 统一定义。

## 1. 项目定位

本项目是“电商 AI 中控台 / 电商自动化控制平台”。

核心能力：
- 多平台、多店铺、多员工、多设备管理。
- 中控台触发 RPA、Python、Node、Browser、EXE 等执行能力。
- Worker 负责设备注册、心跳、任务领取、执行和结果回传。
- Backend 负责业务数据、权限、任务、Session、API、审计。
- Electron 负责桌面壳、本地系统能力和 Worker 进程管理。
- Frontend 负责 UI、交互、状态展示。
- AI 仅用于明确需要的结构化数据分析，不作为基础执行链路的默认依赖。

项目采用：**模块化单体 + 分层文档 + 渐进式演进**。

不要求第一阶段设计所有未来业务，但新增功能必须遵守既定模块边界、契约、抽象与复用规范。

---

## 2. 固定技术栈

除非项目负责人明确要求，否则不得随意替换。

### Frontend
- Vue 3
- TypeScript
- Vite
- Vue Router
- Pinia
- Naive UI
- Axios
- TanStack Vue Query
- vee-validate
- Zod
- Apache ECharts
- dayjs
- VueUse
- Vitest
- Playwright
- ESLint
- Prettier
- pnpm

### Electron
- Electron
- TypeScript
- `contextIsolation = true`
- `nodeIntegration = false`

### Backend
- Python
- FastAPI
- Pydantic
- SQLAlchemy 2
- Alembic
- PostgreSQL
- HTTPX
- pytest
- Redis：按阶段引入
- MinIO/S3：文件存储需要时引入

### Worker
- Python
- 独立于 Electron Renderer 的长期运行进程
- 通过服务器接口注册、心跳、领取任务、回传状态
- RPA / Python / Node / Browser / EXE 作为 Worker 下属执行能力

### 特殊 JS Runtime
- Node.js 仅用于 Electron 或确实需要 JavaScript Runtime 的平台能力
- 禁止无必要地建立第二套 Node.js 业务后端

---

## 3. 系统边界

```text
Frontend
    ↓
Electron Preload / HTTP API
    ↓
Electron Main          Backend API
    ↓                       ↓
本地系统能力             PostgreSQL
    ↓                       ↓
Worker ←────────────── Task / Session / Config
    ↓
RPA / Python / Node / Browser / EXE
```

职责：
- Frontend：界面、交互、路由、前端状态、服务端数据展示。
- Electron：桌面窗口、Preload、IPC、本地文件、进程管理。
- Backend：业务数据、权限、API、任务、Session、Credential、审计。
- Worker：设备常驻、心跳、Task Claim、Lease、执行与结果回传。
- Skill/RPA：完成具体业务能力，不承担中控台业务编排。

禁止跨层偷渡职责。

---

## 4. 分层阅读规则

处理任务前必须先判断修改范围。

阅读顺序固定：

```text
根 AGENTS.md
↓
对应子系统 AGENTS.md
↓
子系统 docs/00-文档索引.md
↓
只读取当前任务需要的专项文档
↓
检查现有代码/组件/契约
↓
再实施
```

### Frontend
涉及 Vue、页面、组件、Router、Store、样式、Design Token、前端 API：
- 先读 `frontend/AGENTS.md`

### Electron
涉及 Main、Preload、IPC、Window、本地文件、进程、打包：
- 先读 `electron/AGENTS.md`

### Backend
涉及 FastAPI、PostgreSQL、Migration、API、权限、Session、Task：
- 先读 `backend/AGENTS.md`

### Worker
涉及 Worker、Heartbeat、Claim、Lease、Skill、RPA、执行日志：
- 先读 `worker/AGENTS.md`

跨系统任务必须分别读取涉及子系统的 AGENTS 和专项 DOCS。

禁止为了“保险”无差别读取所有文档。

---

## 5. 最高优先级实施约束

### 5.1 禁止猜想和自编契约

任何代码修改前必须优先查找：
1. 现有代码。
2. 现有类型。
3. 现有 API Contract。
4. 现有数据库模型。
5. 现有组件。
6. 现有 IPC Contract。
7. 现有 Skill Contract。
8. 对应 DOCS。

禁止自行猜测或创造：
- API URL
- 请求字段
- 返回字段
- 数据库列
- 状态枚举
- IPC Channel
- Event 名称
- Skill ID
- 错误码
- 权限码
- 第三方平台字段
- 配置键
- 文件路径协议

如果权威契约不存在：
- 先确认是否应新增正式契约。
- 新增契约必须落入对应 DOCS / schema / type。
- 仍无法确认的外部事实不得伪造实现，应明确标记阻塞点。

禁止“先随便写一个能跑的，后面再说”。

### 5.2 可以抽象的必须优先抽象

满足任一条件时，必须优先建立抽象层或复用现有抽象：
- 同类逻辑已经出现 2 次或预计会跨页面/跨模块复用。
- 同一业务实体会被多个页面使用。
- 同一种 API 调用模式会重复出现。
- 同一种 RPA / Skill 输入输出遵循统一协议。
- 同一种平台接入存在不同实现。
- 同一种 UI 结构在多个页面出现。
- 同一种 Electron IPC 能力可能被多个页面调用。
- 同一种错误、状态、权限、日志模型会跨模块使用。

常见抽象：
```text
UI → shared/components
领域实体 → entities
业务动作 → features
HTTP → shared/api
后端平台请求 → connector / adapter
外部依赖 → adapter
Worker 执行器 → executor
Skill → standard contract
IPC → typed bridge
```

禁止复制粘贴已有实现形成第二套近似逻辑。
同时禁止无业务依据的“万能抽象”，抽象必须有明确语义边界。

### 5.3 有组件必须优先用组件

实现 UI 前必须先检查：
1. Naive UI 是否已有组件。
2. `shared/components` 是否已有公共组件。
3. 当前领域是否已有可复用组件。
4. 当前页面是否已有一致模式。

存在可满足需求的组件时禁止手写替代。

已有 PageHeader、PageSection、DataTable、StatusTag、EmptyState、ErrorState、LoadingState、ConfirmDialog、ShopSelector、DeviceSelector 等公共能力时，不得创建第二套近似版本。

### 5.4 优先使用成熟第三方库，禁止重复造轮子

已有依赖可稳定解决的问题，优先使用既定第三方库。

典型：
- Router → Vue Router
- Client state → Pinia
- Server state → TanStack Vue Query
- HTTP → Axios / HTTPX
- Form → vee-validate
- Schema → Zod / Pydantic
- Chart → ECharts
- Date → dayjs
- ORM → SQLAlchemy
- Migration → Alembic

禁止手写自制 Router、请求缓存、表单框架、日期工具集、ORM、Migration 等重复基础设施。

新增第三方库前必须先确认现有依赖不能合理解决，避免重复引入同类库。

---

## 6. 复用与依赖方向

优先级：

```text
现有能力
↓
现有公共抽象
↓
现有第三方库
↓
新增领域抽象
↓
最后才是新增一次性实现
```

禁止依赖方向错误：
- shared 不依赖 pages/features。
- entity 不依赖 page。
- Backend shared 不依赖具体业务模块。
- Worker core 不依赖具体某个平台 Skill。
- Electron Main 不依赖 Vue 页面实现。

---

## 7. 核心稳定 ID

长期稳定：
- `user_id`
- `shop_id`
- `device_id`
- `task_id`
- `skill_id`

后续可新增：
- `credential_id`
- `session_id`
- `workflow_id`
- `workflow_run_id`
- `order_id`
- `product_id`

禁止使用店铺名称、电脑名称、员工姓名建立长期关系。

---

## 8. 数据库演进

允许渐进式新增：
- 表
- 字段
- 索引
- 关系
- Migration

修改数据库必须：
1. 先判断是属性、实体还是关系。
2. 通过 SQLAlchemy Model + Alembic Migration 演进。
3. 保持稳定 ID。
4. 不直接手改正式数据库结构。
5. 不让 RPA 直接连接 PostgreSQL。

---

## 9. API / IPC / Skill 契约

所有跨边界通信必须有明确契约：
- Frontend ↔ Backend：API Contract
- Frontend ↔ Electron：IPC Contract
- Backend ↔ Worker：Task/Device Contract
- Worker ↔ Skill/RPA：Skill Contract

契约至少定义：
- 输入
- 输出
- 状态
- 错误
- 版本（需要时）
- 必填/可选字段

禁止调用方自行猜测被调用方行为。

---

## 10. 修改范围

每次任务：
- 只修改当前任务必须文件。
- 不做无关重构。
- 不顺手更换技术栈。
- 不删除架构预留能力。
- 不为单页需求污染全局。
- 不把临时业务塞进 shared。
- 不复制公共组件。
- 不直接跨层调用。

必须跨模块修改时，要说明原因和影响面。

---

## 11. 文档同步

以下变化必须同步 DOCS：
- 目录结构
- 模块边界
- API Contract
- IPC Contract
- Skill Contract
- 数据库核心关系
- Design Token
- 通用组件规则
- 通用状态/错误码/权限码

普通内部实现调整不需要修改全部文档。

---

## 12. 开发前检查清单

- [ ] 已读取根 AGENTS。
- [ ] 已读取目标子系统 AGENTS。
- [ ] 已读取任务对应 DOCS。
- [ ] 已搜索现有组件/方法/类型/接口。
- [ ] 已确认没有重复实现。
- [ ] 已确认字段、URL、状态、权限等不是猜测。
- [ ] 已确认能复用的抽象已复用。
- [ ] 已确认第三方库已有能力优先使用。
- [ ] 已明确本次修改范围。

---

## 13. 完成标准

任务完成不等于“页面能显示”或“代码能运行”。

还必须：
- 边界正确。
- 无重复抽象。
- 无随意硬编码。
- 类型明确。
- 契约一致。
- 错误有处理。
- 验证通过。
- 没有无关改动。

---

## 14. 后端业务层级与身份边界（硬规则）

新的管理端业务能力必须遵守：

```text
API → Service → Repository → Database
```

- API 只负责 HTTP、DTO、参数解析，以及未来 Authentication / Permission Guard 的插槽；禁止承载核心业务流程、直接完成业务写入或跨 Repository 编排事务。
- Service 负责业务规则、状态校验、跨 Repository / Domain Service 编排和事务边界。
- Repository 只负责 Query、Persistence、Lock 与 Pagination；禁止承载权限、UI 语义或跨领域流程。
- Backend 内部的 Scheduler、Maintenance 和未来 Server Job 也必须调用正式 Service；禁止绕过 Service 直接写业务 Repository 或业务表。
- Authorization（例如未来 `schedule.manage`）与业务合法性（例如 Device 已停用）必须分离。权限不得进入 Repository，业务合法性不得交给 Frontend 判断。
- 未来 Data Scope 必须在 API / Query 边界实施；禁止 Backend 返回全量数据后由 Frontend 本地过滤实现数据权限。
- 员工 User Authentication 与 Worker Device Token 是两套独立 Identity；Worker 不使用员工 JWT，员工管理 API 不使用 Device Token。
