# 选品原设计恢复收口：差异核验与 Gate 1

2026-10-12 原记录，81a1 → 集成ca97。2026-10-13 接续状态与最新验证见文末；不倒写历史验收。

## 基线与实际情况

- 开工为 `feat/shop-login-session-sync-v1` / `1178fbfa08fb316ccf5b7310206cd433f5bb24e5`，tracked tree clean。
- 远端及ca97确认 Green `1718abe117c90842c8d39859a074fa988360f070`；该Green包含上述成果，Frontend/Backend业务树一致。
- 旧选品Feature已集成，故从该精确Green建立 `feat/product-selection-ui-restoration-closeout-v1`，不在dev/main开发、不回退旧分支。
- 原设计对照 `06bd03c0fa61b00251063e21350cd0cc5445afe5`；原恢复 `389030a54d219a75fb0b0830fd1e3ccc76235d3e`、后续体验修复 `6e6bfc63f8ee5f3155c134fcb527f44eb9bf4508` 均已包含。
- **当前代码没有再次出现界面替换。** 不制造重复修复：本轮仅追加防回退测试、精确差异/截图/验收缺口记录，Vue运行代码不变。
- 最终Candidate以正式Handoff中的完整SHA为准；截图采用与最终Candidate相同的Vue、service、主题及API代码。

## 06bd03c 至当前代码的差异分类

| 分类 | 差异与当前处理 |
| --- | --- |
| 真实接口适配，保留 | `selection-read-api.ts` / `selection-real-service.ts` 与运行/观察契约；授权店铺真实类目、手动提交、run轮询、数据库候选及详情读取。Real失败不回退Mock。 |
| 真实接口适配，保留 | CandidatePool数据库分页与真实运行状态、详情补充失败原因、来源实际日期和两个独立时间字段；未接手机/百应/策略CRUD不假成功。 |
| 真实接口适配，保留 | 实际发送Cookie签名、同一请求/编码、冻结日期及有限回退、run、事实/来源幂等和Team/Shop权限；本轮Backend及0042/0043无差异。 |
| 曾改变已确认界面，已纠正 | Real整页 `ManualSelection` 替换，以及 `manualOnly` 隐藏策略名称/定时/状态/保存；389030a已删除二者，当前全仓Frontend源代码无引用。 |
| 原页面结构，已恢复且保持 | Real/Mock均使用原StrategyList：搜索、刷新、达人登录、新建策略、原9列、分页、右侧StrategyDrawer。手动结果用既有消息/查询刷新，不再以执行页替代管理页。 |
| 能力限制，不是删界面 | Real保留策略名称、共用达人字段、纵向渠道、定时草稿及hourly/daily/AppTimePicker、状态和保存底栏。未接策略数据不生成演示行；保存/状态禁用，定时明确待接入。立即获取不保存名称、状态或计划。 |
| 类目修复，已恢复且保持 | 当前授权店铺真实树中的有效父级提供“全部”；选择后规范化为该真实父级路径，service仅提交实际行业/有序category IDs，不发送`/*`、0或虚构ID。 |
| 弹层修复，已包含，需原生补验 | NCascader `bottom-start`、Naive/vueuc原生翻转、视口限宽及Token限高；保留纵向列滚动和必要横向滚动。没有自造弹层或页面专属主题。 |

复用原 `FilterBar / DataTable / PaginationBar / AppDrawer / ShopSelector / CategorySelector`，以及
`AppInput / AppRadio / AppSelect / AppSwitch / AppTimePicker`、Naive Collapse/Tooltip和四主题。
不重新设计候选池、详情、字体、尺寸或公共组件。

## 本轮新增回归

`SelectionWorkspace.spec.ts`：手动能力启用/关闭均须保持StrategyList、原工具栏与9列、可打开原抽屉；
无正式策略数据时不调用演示策略读取/保存或隐式提交。显式获取终态、跨Tab返回后仍是原策略管理，不变成结果页。
现有StrategyDrawer测试继续核验名称/定时/状态/保存保留、立即获取不保存、回执Key不因草稿元信息改变。
现有CategorySelector/service测试继续核验父级全部归一化、真实路径提交与串店铺拒绝。

## 实际验证（81a1/frontend）

| 命令 | 本轮结果 |
| --- | --- |
| `pnpm lint` | PASS |
| `pnpm typecheck` | PASS |
| `pnpm exec vitest run src/features/product-selection` | 12文件、84项PASS；正式接口映射、原策略结构、父级全部、手动获取、查询/反馈和权限上下文回归 |
| `pnpm build` | Real production PASS（内含typecheck）；指定选品Mock handler/演示商品标记未进入dist；既有大chunk警告保留 |
| `pnpm exec prettier --check src/features/product-selection/ui/SelectionWorkspace.spec.ts` | 初次格式检查FAIL，机械格式化该测试后PASS；不改运行代码 |
| `PLAYWRIGHT_FRONTEND_PORT=4176 PLAYWRIGHT_API_MODE=real pnpm exec playwright test --config ../.codex/selection-windows-v2/playwright.real.config.ts --workers=1 --trace=retain-on-failure --output=../docs/_local/product-selection-ui-restoration-closeout-v1/real-intercepted` | 3项PASS，1.8m；正式API完全拦截，无Backend/DB/平台调用 |
| `git diff --check` | PASS，最终提交前复核 |

机械格式化后另复跑Workspace 10项、lint及typecheck均PASS。截图测试完成后4176已释放，
未停止或变更5180/8100。测试/截图/运行配置及本地覆盖均已确认Git忽略。

E2E为真实代码的**浏览器契约测试**，不是平台或Electron验收：

- 四主题×960×640、1280×800、1366×768、1440×900、1920×1080，共20个渲染场景（不是20项独立业务测试）。
- 四级菜单实际边界在视口内；50项第四级可滚动到末项并点击；三级“全部”保留真实父级路径。
- 原工具栏、策略名称、定时daily/AppTimePicker、状态/保存及待接入边界；仅手动正式POST、不隐式保存/调度。
- 正式提交使用所选真实树的父级ID；实际备用日期/来源/查询显示、刷新不重复提交；Real无Mock回退、撤权守卫正常。
- 既有NO_COLOR/FORCE_COLOR环境警告保留，不更改环境/业务消除警告。

无需Backend、PostgreSQL、迁移、Signer或真实平台重测，本轮相关代码无改动；未操作任何数据库。

## 前后截图及证据边界

旧06bd原设计截图保留在ignored的 `docs/_local/product-selection-sizing-v1/verified-regression/`；
本轮重新渲染截图在 `docs/_local/product-selection-ui-restoration-closeout-v1/real-intercepted/`。
两者为原Mock设计与当前Real代码/正式API拦截的**结构对照**，数据源不同，不称为真实数据对账。
所有截图CSS缩放100%；不冒称已测到本机原生窗口状态或Windows缩放。
Real尚无策略CRUD，因此列表为空时遵循未修改的公共DataTable空态，不伪造两条演示策略；
原9列配置、工具栏、分页和抽屉保留，不将配置核对冒充空态下有9列表头实际渲染。

- 原结构：`product-selection-strategy-3c099-l-schedule-Baiying-boundary-mock/graphite-strategy-drawer.png`。
- 新原策略列表：`product-selection-strategy-a8313-e-and-parent-all-selectable/graphite-1366-restored-strategy-list.png`。
- 新普通视口四级菜单：同目录 `midnight-960-four-level-menu.png`、`graphite-1366-four-level-menu.png`。
- 新原定时区域：同目录 `graphite-1366-restored-schedule.png`；其他三主题与5视口同命名完整保留。

## ca97 Gate 2 待补（不发布）

本轮Owner代码/定向验证完成；**新的Real Electron复验未通过、也未宣称已经开始**。
ca97确认当前唯一运行窗口为生产店铺登录故障现场，开发Integration Electron已关闭；不得将该窗口冒充选品验收、
停止它以掩盖故障、另开第二验收窗口，或使用上述浏览器证据代替原生结果。

收到正式Handoff后按既有单实例安排加载精确Candidate，核对5180实际源及Real来源，保留合法登录。
在普通与最大化窗口核验原策略结构/定时区域/保存禁用、四级类目可见/滚动/点击、三级全部及实际父级提交。
执行操作仅按既有ca97受控授权；本轮Owner没有新增平台请求，不以界面恢复宣称真实获取失败已解决。
只向用户确认尚未确认的具体尺寸/效果，不要求重新批准整套设计。

以上缺口补齐前不标本轮选品Gate 2或视觉通过，不推进该业务发布。现有已发布事实及历史验收不倒写。
无新Schema/Migration/Slot、无Electron主进程改动，不需要新桌面安装包。
回滚仅可正常revert本轮测试/文档提交，不回退业务底座、清库或改写0042/0043。

## 2026-10-13 原分支接续与本轮 Gate 1

用户再次明确暂停当前登录诊断及关闭恢复返修，优先本项；仅适用于81a1当前工作，不扩大为其他会话全部暂停。
开工 `feat/shop-login-runtime-diagnostics-v1` / `98d48d4e12bc080e209fa488299e0cd774c6dd6f`，工作树干净。
登录候选、匹配安装包、关闭恢复缺陷证据、全部旧分支/忽略材料和数据库成果保留。
ca97与实际fetch均确认Green `22403a1094b25b7569427d5383e4e28154253d79`，main `db4ca95671348b38dc2d0414ace49a4fab88b181`。
原恢复候选 `1279cc9ee71eaab52c0a76e86940edac12f53d0d` 尚未集成，故沿原恢复分支继续；
以正常merge同步Green，提交 `ab44925f38d1423d9c0d6c0332e41e3a10441c1d`，两处任务/资源登记冲突保留双方历史并明确本轮优先级，未改写历史。

对06bd03c的分类和恢复依据沿用上表，经当前源码复核：没有ManualSelection/manualOnly，
原StrategyList/Drawer、工具栏、策略名称、定时草稿、状态和保存入口均在；保存/调度未接入不假成功。
正式手动提交、店铺类目树与父级全部、Signer、有限日期回退、run、事实及来源、API和Team/Shop权限保持。
相对上述Green，除 `SelectionWorkspace.spec.ts` 外，选品运行源码、公共组件、Backend及Electron无差异。
不因新的提交SHA重做已确认的界面；本轮新增两项查询失败回归，确认能力/进度读取失败仍保留策略管理及原抽屉，
不隐式读取演示策略、保存草稿、创建运行或显示成功。保留1279的启用/关闭能力及获取完成后仍为原页面的测试。

| 实际命令（81a1/frontend） | 本轮结果 |
| --- | --- |
| `pnpm lint`、`pnpm typecheck` | PASS |
| `pnpm exec vitest run src/features/product-selection` | 12文件 / 86项PASS，14.34s |
| `pnpm exec vitest run src/features/product-selection/ui/SelectionWorkspace.spec.ts` | 格式化后12项再次PASS，7.85s |
| `pnpm exec prettier --check src/features/product-selection/ui/SelectionWorkspace.spec.ts` | 初次FAIL；仅机械格式化新增测试，最终PASS |
| `pnpm build` | Real production PASS，20.88s；包含typecheck，指定Mock模块/演示商品标记扫描0匹配；既有大chunk警告保留 |
| `PLAYWRIGHT_FRONTEND_PORT=4176 PLAYWRIGHT_API_MODE=real pnpm exec playwright test --config ../.codex/selection-windows-v2/playwright.real.config.ts --workers=1 --trace=retain-on-failure --output=../docs/_local/product-selection-ui-restoration-closeout-v1/20261013-real-intercepted` | 3项PASS，1.9m；所有正式API拦截，未启动Backend、写DB或调用平台 |
| `git diff --check`、本地覆盖/截图/运行配置Git忽略检查 | PASS；4176测试后已释放 |

本轮实际截图为Real代码配正式API拦截夹具的**浏览器结构证据**，非平台实测、非Electron。
四主题×960×640、1280×800、1366×768、1440×900、1920×1080；四列在视口内、50项第四级滚动/点击、
三级全部、原定时daily/AppTimePicker、状态/保存禁用以及正式父级提交/实际备用日期/刷新不重提/撤权守卫均通过。
截图已与既有06bdMock原设计对照，数据源不同，不冒称同数据对账；完整路径见本轮正式Handoff。
本轮输出在上述 `20261013-real-intercepted`，旧截图/报告完整保留；NO_COLOR/FORCE_COLOR警告如实保留。

ca97确认当前唯一Real Electron为98不可变登录预览，5180→8100→Integration单一0043；
其中选品运行代码仍是Green既有树，不是本轮候选加载证据。原生普通/最大化四级菜单和父级全部独立尺寸证据仍未取得。
收到本轮精确Candidate后，由ca97按单实例流程加载/核验对应Real代码，保留合法登录；不另开Electron、
不覆盖当前故障现场、不以本轮浏览器截图代替原生Gate。只补具体尺寸和操作，不要求重新批准整套设计。
新的真实获取失败继续独立定位，本轮界面保留及合成测试不声称其已修复；未完成原生专项前，本项Gate 2/视觉仍待验、不得发布。
本轮无新Schema/Migration/Slot，无新的业务数据库或桌面壳改动，无需新增桌面包。
