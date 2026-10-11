# 选品原设计恢复收口：差异核验与 Gate 1

2026-10-12，81a1 → 集成ca97。本轮用户要求暂停原任务，先核对已确认选品设计，不追加业务或发布。

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
