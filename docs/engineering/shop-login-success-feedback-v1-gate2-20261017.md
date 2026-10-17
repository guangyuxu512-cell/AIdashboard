# 登录成功提示集成验收

精确候选 `e6f68d2be01b1024a258425498eb39c2b60bf38e` 已通过适用 Gate 2、精确 dev/main CI 和 Release Gate，正式生产为 `fe7ce217dfee8a0bf3374c6da42a902d20ad9e4d`。新增提示的原生人工观察仍为 `NOT_OBSERVED`，不把技术或发布检查冒称新登录、窗口或平台验收。

## 范围与基线

候选分支为 `feat/shop-login-success-feedback-v1`，直接父为已验证 Green `08176d9c5cdbea50114eb0656975a209205761bd`。远端候选一致。相对基线仅有 8 个路径：3 个店铺管理 Renderer 运行文件、对应 3 份测试、前端契约及 Gate 1 记录。

本次只保留当前保存事件的版本与时间回执，并区分保存成功后查询刷新失败。Backend、Main、Preload、IPC、poller、Shared、实体 API、全局消息、依赖及 Migration 无变化。两个 Vue 的 style 块逐字不变，原 96px 状态格、small 标签和操作顺序保留。

原 98 分支、已发布 998/P、1.0.8 包、Profile、Session、共享 stash 及 ca97 本地 `6b326033f8d2d06547380f55074240b2e3358cc4` 治理提交均保留；不整条合并旧 98，不重置或改写历史。

## 独立验证

| 验证范围 | 结果 |
| --- | --- |
| 归档与源码 | 8 个变更 blob 与候选一致；两个 Vue style 块与 Green 相同 |
| 前端定向单元测试 | 84 PASS，0 FAIL，13.638 秒；包括真实 QueryClient 和 QueryObserver 的合成读取失败分支 |
| lint 和 typecheck | PASS，分别 9.271 和 25.061 秒 |
| 精确 Real 构建 | PASS，16.683 秒 |
| 新构建隔离浏览器 | 4 PASS，0 FAIL，13.409 秒；1280×800、1920×1080，以及列表和详情 Session 的 503 分支 |
| 未变桌面运行码 | 候选 Electron tree `2c99c91538d10df75a5c303c190424e98b429830` 与正式 Source P 相同；16 个编译运行文件与已核 1.0.8 匹配 |

浏览器使用精确候选的 Real 构建，API 与桌面桥接均为完整拦截，不访问实际 5180 服务、数据库、Profile 或平台。验证了短消息消失后标签与时间仍可查看、详情回执、读取失败保留保存事实与 ErrorState、原行高和状态格宽度、再次置前不新增保存、刷新不重播历史消息。它是本候选的新技术证据，不是原生人工证据。

此前 998/P 的真实身份、错店保护、Session 自动保存与服务端可用性、无团队授权、留窗置前及安装交付，只复用于本次未变路径。生产 `51a5bd34b1af33fc3ad3b876cb107a1964c440fa` 和 1.0.8 已收口，不重开三轮专项。

## Gate 适用性裁决

`01-开发集成与发布流程.md` 第 3 节要求按候选完成必要的独立集成验证，接受后才正常 no-ff 合入 dev 并复验；第 4 节要求完整 Gate 记录和 Green 后另行 Release Gate。`frontend/docs/07-开发与验证规范.md` 要求按影响范围执行 lint、typecheck、unit、build 及关键交互 Playwright。这些规则没有把每个纯 Renderer 提示变更都规定为一次新的真实登录或平台请求。

候选 Gate 1 的原生未覆盖说明是交接事实，必须保留，但没有新增一条高于现行流程的强制登录规则。本次不改原生窗口或跨进程契约；未变真实链路已有直接验收，新增局部状态和提示有上述独立组件、真实查询库与精确构建浏览器覆盖。因此 ca97 判定适用 Gate 2 通过，可进入正常合并、合后复验和精确 dev CI。这是按改动范围作出的验收裁决，不修改规则，不把“不要重复”当作人工 PASS 或门禁豁免。

保留的限制是：新增标签、Tooltip、详情 NAlert 和保存后读取警告，尚未在唯一原生 Electron 中由本次新保存事件触发后人工观察，状态仍为 `NOT_OBSERVED`。不能用旧真实登录、jsdom、浏览器截图或历史元数据改写这一事实。新增分支没有已确认缺陷；若后续实际出现提示问题，按 Feature 修复和正式前端版本回退处理。

已直接核对用户在规划 turn `01a1477a-fddd-7331-8351-c49266d0a575` 的“已经退出。不要在重复那个窗口任务”，取消待执行的再次登录、切店、关窗安排，0 新 refresh 预算。后续 turn `01a14788-0c80-7b73-be1a-36ad46a23793` 明确要求继续分配推进；本次不再安排窗口或向用户提出重复操作。

## 合并与发布边界

先保存既有治理工作，再正常 `--no-ff` 合入精确候选并复验。只有合后检查、干净工作树及该精确 dev 的 CI 成功后才标 Green；结果在本节补记，不用本地检查代替 CI。

既有治理已保存为 `6ef6dcc`，原 `6b326033` 完整保留。候选正常 no-ff 合并为 `15980a6ed866e6e7b5094201314f725e6db34671`，8 个候选 blob 与工作区逐一一致；Backend、Electron、Shared、entities 和 app 子树仍与原 Green 相同。

合后从实际 dev 源码复验：84 项 PASS，lint、typecheck、Real build 全部 PASS，构建 17.759 秒；同 4 项全拦截浏览器 PASS，13.349 秒。首轮本机测试夹具因 CommonJS 模式不能加载 import.meta，在执行用例前停止；只修正 ignored 夹具的模块模式，首轮日志和报告保留，未改业务、测试断言或规则。合后证据位于本地忽略目录 `.codex/gate2-feedback-postmerge-15980a6e/`，无新窗口、平台、数据库或 Profile 操作。

运行代码已推送于 `031732bce37a9f231be4fa2ceebb81ec66c93ab1`，[CI 38992808421](https://github.com/guangyuxu512-cell/AIdashboard/actions/runs/38992808421) 的 Backend、Frontend Real build 和 Container runtime 三项全部 success。随后仅更正商品数据资源的共享集群事实与实际访问阻塞，运行源码不变；后继治理提交仍须等待其自身精确 CI 才作为最终 Green，不把前一 CI 冒充后继提交结果。

Migration Slot：无，单一 `20261015_0046` 不变；不访问或迁移数据库。不需要新 Electron 包，不修改已安装 1.0.8。前端回滚使用正常 revert 或正式前端版本恢复，不清 Profile、Session、缓存事实或降库。

人类在规划 turn `01a1479d-e1b2-7883-af8e-e3e6fc26758f` 对“单独部署登录提示、不含商品数据、不换安装包、不重复登录窗口测试”明确回复“可以”。Main 为唯一发布执行者；商品数据 UI、真实实现和0047不混入本次运行代码。

## 正式发布结果

最终 Green 为 `bef7093b755cea60fda55bbcc6177b5723d4738a`，[dev CI 38993305361](https://github.com/guangyuxu512-cell/AIdashboard/actions/runs/38993305361) 三项 success。Main 正常 no-ff 合入并推送 `fe7ce217dfee8a0bf3374c6da42a902d20ad9e4d`；[main CI 38994152520](https://github.com/guangyuxu512-cell/AIdashboard/actions/runs/38994152520) 三项 success，[唯一自动部署 38994375587](https://github.com/guangyuxu512-cell/AIdashboard/actions/runs/38994375587) attempt1 success，于北京时间2026-10-17 10:21:50完成。ca97已独立核对两条流水线的精确 SHA、结论及远端 main；未再次调度部署。

Main 实机回执确认 current 及 Backend、Frontend、Signer 镜像均为同一 fe7ce217，Backend/Signer healthy，Frontend/public HTTPS/index与入口静态资源正常。旧51a5及历史hash资源保留，缺失JS为真实404；mounted/CIFS及应用权限正常。生产仍单一 `20261015_0046`，商品Feature的0047未发布。

10:13:20与10:22:17的12表逐行摘要全部 exact-match，包含全部ShopSession；4条Schedule原值、已停用三小时计划及空next_run_at保持，原每日Asia/Shanghai 09:00、配置文件字节与0600权限均不变。新备份1187478字节、restore目录355项可读，SHA256为 `87bdcef83776b339c3779c9e495e886de4569b2b15316ba3bc33cab417960804`；旧51a5发布目录及三镜像仍保留。

实机证据由Main保存在 `D:/中控台/.dev-runtime/shop-login-feedback-release-20261017/server-release-receipt.json`。正式1.0.8/P安装包和用户窗口未动，0新增login、validate、平台或RPA请求。新增反馈原生视觉继续记 `NOT_OBSERVED`；未变998/P专项证据复用。本功能按已批准范围完成发布收口，不再向main补提交引发部署。
