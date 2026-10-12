# 选品库前端与 Mock 交互 V1

## 2026-10-13 策略 A Real 绑定（当前开发）

本轮保留已确认列表/工具栏/右抽屉及五项体验，不用手动结果页替换策略页。
正式契约来自Backend `strategy_contract.py`，typed API集中在selection-strategy-api.ts；
已有service、TanStack Query、ShopSelector、CategorySelector、AppRadio/TimePicker/按钮复用。
服务器分页/名称搜索、保存/完整编辑expected_version、启停CAS接线；刷新/重新登录只GET。
策略名称/相对条件/全策略定时配置/状态真实保存，无“演示策略已保存”Real提示。
RealCRUD能力与演示/手机动作的available分开，候选采集/屏蔽/竞品等未接能力仍禁用，不因保存
接通而假成功。A计划只保存，列表明确“未调度”、抽屉提示调度待接入；无假next_run_at。
立即获取经原manual服务提交当前草稿及已保存策略ID/version，未保存草稿不创建策略、不保存条件。
收到canonical后沿原消息/轮询刷新最近结果，历史完成不重复toast；不恢复常驻获取完成横幅。
支持已确认短视频近7天、默认品牌价格、原bool首次上榜返回筛选、有界官方排名1–200；
未知日期/品牌/价格/其他行业不解除禁用、不回退Mock。来源首次上榜口径与原scope分开。
详情/候选池尺寸、主题、字体和两个时间来源不改。API拦截截图不是平台/数据库/Electron证据。
完整本轮契约见docs/engineering/product-selection-strategies-v1-contract.md；A仍PARTIAL，
下方旧UI_ONLY/未接保存为历史阶段，B服务端自动执行尚未接通。

状态：视觉/Mock为UI_ONLY，手动真实接入为PARTIAL。下述Mock模型仍是前端草案；文末“正式只读绑定”以已登记Backend DTO为准，不混用。
Green 基线：`b34e43cb90356e03d2f793c4146c6775a11f5ab3`（ca97 确认精确 CI PASS）。
分支：`feat/product-selection-frontend-v1`。当前前端返修阶段无 Backend、数据库、Migration、Electron 壳、真实平台或调度变更。用户已授权在前端确认后接续真实手动闭环；该阶段须另登记契约、Feature DB/Migration及真实验证，不能用本阶段证据宣称完成。

当前表现以文末“候选池与详情视觉收口”“文字层次与详情顶部时间返修”“审核返修与无用残留清理”“候选池图片与列宽尺寸收尾”及“正式只读绑定”为准；此前各轮不同列宽、尺寸、对齐、更多菜单及常驻说明仅为历史验收记录。

## 实施前复用清单

| 现有路径（frontend/src） | 用途 | 新增边界 |
| --- | --- | --- |
| shared/components/ContextSwitchBar.vue | 保留 framed 三选项和 query 历史 | 不改公共切换组件 |
| shared/components/ManagementListSection.vue、FilterBar.vue、DataTable.vue、PaginationBar.vue | 两种列表、稳定底部分页、固定列、列对齐 | DataTable仅透传已有themeOverrides，其他调用默认不变 |
| shared/components/DetailDrawer.vue | 商品详情 | 仅新增选品指标内容 |
| shared/ui/AppDrawer.vue、AppButton.vue、AppSelect.vue、AppInput.vue、AppNumberInput.vue、AppSwitch.vue | 策略右抽屉、条件与独立保存/立即获取 | AppButton增加可选small、保留默认medium；组合已有footer，不改变FormDrawer |
| shared/ui/AppCheckbox.vue、AppRadio.vue、AppTimePicker.vue；Naive NCollapse/NCollapseItem | 选择渠道、日期四选项/价格模式、每日时间、纵向折叠 | 日期仅参考经营看板组件用法，不复用其统计日期算法；不新建控件 |
| Naive NText、NEllipsis；Lucide Copy | 缺值/辅助层次、标题单行溢出与全文提示、ID 同行图标 | 继承 themeOverrides，不为页面另配色，不另建复制组件 |
| shared/components/TableToolbar.vue、原生 checkedRowKeys | 当前页选择数量、批量演示与逐项失败反馈 | 不建立跨页暗选或第二套选择控件 |
| entities/shop/ui/ShopSelector.vue | 请求店铺 | 不建立第二套店铺选择 |
| shared/styles/tokens.css、app/providers/naive-theme.ts | 四主题/字体/密度 | 不新增 token 或单页配色 |
| shared/composables/useAutoSearch.ts、TanStack Query | 显式列表搜索与请求隔离 | 不建立新缓存/搜索框架 |
| entities/asset/ui/AssetPreviewDialog.vue（核对但不直接复用认证取图） | 现有放大预览交互参考 | 外部商品图组合 Naive NImage，原资产链路不变，禁止使用认证 HTTP Client |

仓库无 NCascader 封装。选品 Feature 内 CategorySelector 只薄封装现有 Naive 多列级联，各父节点增加明确的“全部”选项（ID 后缀 `/*`），不创建基础控件框架。
新增领域类型、service、Mock handlers 与业务组件，是因为当前只有占位，没有选品契约/业务内容。路由与模块授权继续原注册，不增加权限码。

## 数据与能力边界

契约权威为 `features/product-selection/model/contracts.ts`，集中约定字符串 ID、nullable 指标、原始区间、页码、排序、条件及演示回执。不定义猜测的 HTTP URL。
Mock service 仅在构建环境明确 `VITE_API_MODE=mock` 且调用模式为 mock 时加载；读写只在内存，刷新恢复夹具，账号/团队变化重新隔离，三个切换项之间保持本次内存数据。Real service 不加载 Mock，不发任何选品网络请求，明确返回未接入能力。
达人账号只有演示选项，无真实登录。工具栏登录入口报告未接入，不开假页面。立即获取只返回该店演示夹具数量，并更新已保存策略的演示最近结果；不声称模拟了平台完整条件匹配，百应不编造结果。定时配置只保存演示规则，不启动后台任务。
商品外部图通过浏览器图片加载/Naive 预览，不使用系统 axios、认证 Header 或 X-Team-ID。缺失与失败单独展示并可重试。

## 请求草案

- categories(shopId)：行业/层级树；允许父级全部，选项 ID 保持字符串。
- list/save strategies：命名策略、请求店铺、共用达人、多个渠道配置、全策略唯一的 enabled/hourly/daily schedule。
- `channels.shortVideo = {selected, conditions}`：条件独立包含请求类目、日期、品牌、价格及结果筛选首次上榜/排名。`channels.baiying = {selected, conditions:{}}`：未知条件严格为空，不接纳猜测字段。至少选一个渠道。
- 两个渠道纵向折叠，展开状态仅为 UI 状态，不参与保存；折叠、取消选择不清条件。切店只清当前短视频失效类目。草稿深拷贝，列表缓存与其他策略不会被编辑污染。
- retrieve(input, strategyId?)：允许未保存策略；选中的短视频返回演示回执，百应返回 unavailable/count=null。仅选百应明确失败，同时选择时返回部分演示回执；不会把百应计入完成数量。编辑抽屉传入已有策略 ID 仅更新最近演示结果，成功后使用现有列表 Query 刷新；不保存未提交的条件。新建草稿不传 ID、不创建策略。不是平台采集成功。
- list/get candidates：先完整筛选，再原始日期/差评率排序（null 双向末尾、同值 ID 稳定），再分页。列表只返回 PageResult；来源与统计区间保留在每条商品的 sourceContext，不再提供列表 contexts 汇总或商品顶层重复 statisticalPeriod。
- demo action：屏蔽/恢复仅修改 Mock 池；“采集资料”只改变演示状态，不请求平台/手机、不写正式商品库。
- `collectBatch(candidateIds)`：前端草案，输入为当前勾选候选 ID；按字符串 productId 去重，`results` 每个商品一项，包含 `candidateId/candidateIds/productId/state/message`。同商品多个候选别名共同回填；不存在的候选 productId=null、failed。成功与失败均返回，单项失败不终止其余项。单条与批量使用同一 collect 规则；mode 固定 mock、成功态名 demo，不声称正式入库。
- 批量成功项取消勾选，失败项保留并逐项显示原因；请求级失败保留全部选择，执行中互斥。全选只作用当前页，换页/搜索/筛选/排序清空选择。Real collectBatch 与其他业务能力同样明确不可用，不调用猜测接口。
- 日期仅有实时/近1天/近7天/近30天，策略持久化草案只存相对周期 `realtime/1d/7d/30d`。`previewPeriod(period)` 返回 `{mode:'mock', rangeLabel}`，仅展示固定 Mock 示例区间，不写入策略或获取参数；Real 明确不可用，不解析未知的平台实际日期。原始支付金额单位不猜测、不换算。

Real 后续手动闭环须先冻结 Backend/OpenAPI、团队与店铺授权、罗盘榜单及basic_info请求/响应/单位契约，并申请必要Feature DB和Migration Slot；不能直接把本草案 URL 化。短视频/罗盘复用店铺ShopSession，不以达人Session或自动调度为前置；百应与定时监控留在独立后续范围。

短视频/罗盘渠道的请求店铺与达人身份分离：仅选择短视频时 creatorId 可空；选择百应才要求对应达人。未知百应能力依然不可用，不将通过表单校验等同于真实接口接入。

## 原候选 Gate 1 验证（02ce8808；不替代本轮返修验收）

执行位置为 81a1，浏览器地址 `http://127.0.0.1:4176`，Vite `--strictPort`。未启动 Backend、数据库或 Electron，不占用 Integration 5180/8100。

| 命令（frontend 目录） | 实际结果 |
| --- | --- |
| `pnpm lint` | PASS |
| `pnpm build`（含 `pnpm run typecheck`，强制 Real production build） | PASS；无 selection-mock-handlers 构建 chunk。既有大 bundle 提示仍存在，未扩大到性能重构 |
| `pnpm test` | 130 个文件、531 项 PASS；既有 jsdom XHR AggregateError stderr 未造成失败，不把它记为零告警 |
| `pnpm exec vitest run src/features/product-selection src/shared/components/DataTable.spec.ts` | 3 个文件、16 项 PASS |
| `PLAYWRIGHT_FRONTEND_PORT=4176 pnpm exec playwright test --project=mock e2e/product-center.spec.ts e2e/product-selection.spec.ts --workers=1` | 4 项 PASS：导航/history、四主题与 AI framed 对照、候选全量排序分页/图片预览/屏蔽恢复、策略抽屉/父级全部/校验/独立立即获取/hourly 与 daily 保存回读/百应不可用 |
| `PLAYWRIGHT_FRONTEND_PORT=4176 pnpm exec playwright test --config playwright.selection-real.config.ts --workers=1` | 1 项 PASS：Real 不回退、不请求选品接口，普通团队取消模块权限后拒绝直达。仅拦截现有登录/团队/权限 API，没有假设后端业务接口 |
| `git diff --check` | PASS |

候选列表使用原生降序→升序→取消排序，字段限上架日期/差评率；默认恢复夹具顺序，同值按字符串候选 ID 稳定，null 双向末尾，真实 0 参与排序。

## 第一轮视觉与多渠道返修（1211c34，列宽/标题由第二轮覆盖）

本轮覆盖原候选缩略图/单渠道方案，其他有效流程保留：

- 候选列：复选框44、图片104、店铺140、标题320、商品ID160、类目150、价格100、日期140、差评率100、操作200。默认10条，完整结果排序后分页。
- 只固定复选框/图片及右操作，减少 1366 宽窗口固定区对标题的挤占。标题最多三行且可查看全文；商品ID保持19位字符串，独立复制完整值。
- 商品照片80×80，object-fit:contain，不拉伸；这不是表单控件尺寸，不修改公共表格 padding/行高 token。图片内容自然撑高商品行，其他表格不受影响。
- 10张本地 WebP 来源及边界见 `features/product-selection/fixtures/README.md`；正常列表不含失败图。图片放大继续 NImage，失败在专门测试注入。
- 第一轮曾使用日期 AppSelect（本轮收尾已由 AppRadio 四选项覆盖）、价格 AppRadio、每日 AppTimePicker。两渠道纵向折叠，共用顶部店铺/达人，仅一套启用/定时。
- 缺值使用 NText depth=3，最近演示结果 depth=2，其余正文继承主题。未发现并未新增硬编码黑色；四主题的实际渲染仍需检查，不以属性测试替代。

返修验证及前后截图保存在 `docs/_local/product-selection-frontend-v1-repair/`，
原候选材料保留于旧目录。新候选另记实际执行结果，Electron Gate 2 未完成前不宣告视觉通过。

### 返修 Gate 1 实测

均在 81a1 执行，浏览器 `127.0.0.1:4176 --strictPort`，未使用 Integration 端口或新增 Electron：

| 命令（frontend） | 结果 |
| --- | --- |
| `pnpm lint` | PASS |
| `pnpm build`（含 typecheck，Real production） | PASS；无 Mock handler chunk、无商品 WebP 夹具，既有大 chunk 告警保留 |
| `pnpm test` | 130 文件 / 534 项 PASS；最后详情缺值展示属性调整后另复跑受影响回归及 build |
| `pnpm exec vitest run src/features/product-selection src/shared/components/DataTable.spec.ts` | 最终 3 文件 / 19 项 PASS：多渠道深拷贝、保存回读、未保存获取、边界、折叠、类目失败重试/切店竞态、全量排序分页及 Real 隔离 |
| `PLAYWRIGHT_FRONTEND_PORT=4176 pnpm exec playwright test --project=mock e2e/product-center.spec.ts e2e/product-selection.spec.ts --workers=1` | 最终 5 项 PASS，54.4s：原导航/守卫回归、四主题共享 framed 对照、10张照片/80px/19位复制/横向固定/全量排序分页/预览/屏蔽恢复、双渠道条件保存回读/折叠/单套定时/时间控件/禁用态、独立外图失败与原图重试 |
| `PLAYWRIGHT_FRONTEND_PORT=4176 pnpm exec playwright test --config playwright.selection-real.config.ts --workers=1` | 1 项 PASS，5.3s：Real 无业务请求/无 Mock 回退，普通团队取消权限后守卫拒绝 |
| `git diff --check` | PASS |

浏览器截图已人工对照：四主题候选池、横向滚动、店铺参考表格、主抽屉、双渠道折叠总览/展开/底部滚动、
下拉弹层、禁用条件、详情及 Real 不可用。候选表普通正文计算颜色与对应主题店铺表相同；
缺值采用不同的公共次要文字颜色。计算值由 Playwright attachment 记录，不用主题属性断言替代截图。
核对既有 ShopFormDialog / DeviceFormDialog / ScheduleFormDialog 均沿用公共控件、次要文字 token，
本轮不改变它们或共享 token。新 UI 的右抽屉宽度、输入高度和底栏来自 AppDrawer/公共表单；
只放大商品图片内容，不调整公共表格尺寸。

未完成：ca97 的唯一 Integration Electron 新候选验收及用户视觉确认；前端契约仍为草案，
百应条件、真实匹配、真实图片业务来源、平台接口、达人登录/Session、后台调度及持久化仍未接入。
本轮不触发业务或生产发布，不需要新 Electron 安装包。

实际浏览器截图（四主题、1366×768、横向滚动、策略列表、右抽屉、详情、填值后抽屉滚动、Real 不可用）保存在忽略目录 `docs/_local/product-selection-frontend-v1/{mock-browser,real-browser}/`。截图已检查，但不是 Electron 验收。

未执行项：唯一 Integration Electron 的视觉/操作验收由 ca97 在 Gate 2 完成；真实平台条件匹配、类目 API、达人登录/Session、持久化策略、正式采集/入库、后台定时与手机能力均未接入。平台实际日期区间、金额单位保留未知。百应条件为空且不生成模拟取数结果。

## 第二轮定向返修

接续 `1211c34dc195e89cf93d85a2c956ae272f7bfd1c`，保持 10 条分页、真实照片夹具、80px 等比例图片、独立多渠道条件与全策略唯一执行计划。

- 当前列宽：复选框44、图片104、店铺140、标题240、商品ID200、类目140、价格100、日期140、差评率100、操作200，总宽1408。标题单行 NEllipsis/Tooltip，不要求长标题全部展开；ID 与 Copy 图标同行居中，保留完整字符串复制和成功反馈。
- 详情复用 DetailDrawer、ExternalProductImage、NDescriptions，补齐图片、店铺、类目、价格带、日期、差评率及屏蔽状态；原来源、周期、排名、首次上榜与四项原始区间不变。列表/详情共用业务格式化函数，null 显示 —，真实0正常显示。
- StrategyDrawer 继续公共 lg 宽度，NForm 同行标签96px；店铺/达人、日期/品牌、价格上下限、排名起止使用原双列容器。不新增页面 CSS、字号或宽度补丁。渠道纵向折叠，定时与启用仍各一套，AppTimePicker 不变。
- 故障注入回归修正了单项异常回执丢失已知 productId 的问题；正常 Mock 列表不混故障样本。浏览器异常测试只拦截开发 Mock 模块/外图，不增加生产故障开关或猜测业务 URL。

本轮实际渲染材料使用 `docs/_local/product-selection-frontend-v1-repair-2/`，前后对照保留 1211 的原目录。
浏览器为 Feature `127.0.0.1:4176 --strictPort`；四主题1366×768，另核对1920×1080候选与抽屉。
截图等待有限过渡动画结束后捕获，不把折叠过渡空白当正式状态。
Gate 1 的执行结果与精确新 Candidate 记录在同目录 Handoff；旧候选记录不替代本轮验收。
唯一 Integration Electron 及用户本轮视觉确认仍由 ca97 接续，未完成前不标视觉 PASS、不发布。

### 第二轮 Gate 1 实测

| 命令（frontend） | 结果 |
| --- | --- |
| `pnpm lint`、`pnpm typecheck` | PASS；build 再执行 typecheck |
| `pnpm test` | 132 文件 / 538 项 PASS；最后异常回执修正后另复跑定向回归 |
| `pnpm exec vitest run src/features/product-selection src/shared/components/DataTable.spec.ts` | 最终5文件 / 23项 PASS；含去重、单项/请求级失败保留选择、互斥、详情缺值及原多渠道/竞态回归 |
| `PLAYWRIGHT_FRONTEND_PORT=4176 pnpm exec playwright test --project=mock e2e/product-center.spec.ts e2e/product-selection.spec.ts --workers=1` | 最终7项 PASS，1.2m；四主题、单行 Tooltip/19位复制/同行居中/固定列，当前页批量空选/成功/部分失败/快速双击，详情缺值/预览/故障，紧凑抽屉及原双渠道/计划/history |
| `PLAYWRIGHT_FRONTEND_PORT=4176 pnpm exec playwright test --config playwright.selection-real.config.ts --workers=1` | 1项 PASS，10.2s；Real无Mock/无猜测请求，团队撤权后守卫拒绝 |
| `pnpm build` | PASS（Real production）；无商品照片/Mock handler夹具产物；既有500kB chunk告警保留 |
| `git diff --check` | PASS |

迭代中新增故障注入曾发现失败回执丢失商品ID，已修复并复跑；截图中过渡态已改为等待状态稳定。
全量单测既有 jsdom XHR AggregateError stderr、Playwright NO_COLOR/FORCE_COLOR 和构建大chunk告警如实保留，不作零告警声明。
本轮截图及计算颜色已检查，不改变主题token。实际Electron与用户视觉确认未执行；无后端/数据库/真实平台测试需求，不冒称业务接入完成。

回滚：未涉及 Schema、数据或 Electron 壳变更；候选失败退回本 Feature，集成后回滚使用明确 revert，不改共享历史。无需新桌面包。状态为“前端／Mock完成，待 Gate 2”，不是选品业务完成或生产发布。

## 日期交互收尾（接续4b7fd7d）

- 日期改为公共 AppRadio 横向四项：实时/近1天/近7天/近30天；删除旧日期下拉及额外选项/提示逻辑。不更改共享组件、主题 token、字号或抽屉宽度。
- 原等宽双列实测日期空间约242px，四项需要约260px；仅日期/品牌区域组合既有 Naive NGrid/NGi（7:5），其他双列布局不变，无新增页面 CSS。1366与1920视口仍能同排。
- Mock 示例区间由隔离 Mock service 返回固定夹具，不使用经营看板的上海日期算法，也不声称真实平台日期契约已确认。示例文字使用公共 NText depth=3，策略保存与立即获取仍只传相对周期，不附加预览日期。
- 期间切换使用现有 TanStack Query 的上下文/周期键；折叠与禁用保留条件，取消编辑不修改已保存策略。Real 无正式接口时保持不可用，不展示 Mock 示例或虚假成功。
- 本轮继续回归候选池/批量/详情；成交件数仍为原始区间，不增加“近30天销量”或佣金/达人接口数据。
- 运行结果、四主题实际浏览器截图及精确 Candidate 记录于 `docs/_local/product-selection-date-repair/`。浏览器证据不替代 ca97 唯一 Integration Electron 与用户复验；未确认不标视觉通过、不发布。

### 日期收尾 Gate 1 实测

执行位置为81a1；浏览器 `127.0.0.1:4176 --strictPort`，未启动Backend/数据库/Electron，未占用集成端口。

| 命令（frontend） | 结果 |
| --- | --- |
| `pnpm lint`、`pnpm typecheck` | 最终 PASS |
| `pnpm test` | 132文件/543项 PASS；最后示例文字改为块级、测试类型注解修正后另复跑定向回归 |
| `pnpm exec vitest run src/features/product-selection src/shared/components/DataTable.spec.ts` | 最终5文件/28项 PASS，8.94s；四周期Mock区间/只存相对值、禁用/折叠保值及候选批量/详情/类目竞态 |
| `PLAYWRIGHT_FRONTEND_PORT=4176 pnpm exec playwright test --project=mock e2e/product-center.spec.ts e2e/product-selection.spec.ts --workers=1` | 最终8项 PASS，1.6m；四主题1366/1920、四项互斥/保存回读/取消、原候选池/批量部分失败/详情缺值/图片故障、导航 |
| `PLAYWRIGHT_FRONTEND_PORT=4176 pnpm exec playwright test --config playwright.selection-real.config.ts --workers=1` | 1项 PASS，5.4s；无Mock模块加载/示例区间/虚假成功或猜测业务请求，普通团队撤权守卫正常 |
| `pnpm build`、`git diff --check` | 最终 PASS；Real产物无Mock handler、商品照片或固定日期示例夹具 |

迭代曾修正测试点击Radio隐藏输入的定位，以及测试AppOption注解过窄引起的typecheck失败；最终已通过。
完整单测既有jsdom XHR stderr、Playwright NO_COLOR/FORCE_COLOR和既有大chunk告警如实保留。
本轮没有改候选池/详情业务代码、公共日期组件/主题、经营日期算法或Electron壳；无DB/Migration/真实请求/达人登录测试需求。唯一Electron视觉验收仍待ca97与用户完成。

## 候选池与详情调整（接续 d7cf900a，2026-10-09）

状态仍为 UI_ONLY。列表依次为勾选、缩略图、商品标题、店铺名、类目、榜单排名、发现情况、价格/价格带、差评率、首次上架日期、采集状态、操作。保持10条、80px图片、单行标题/Tooltip、排序先全量后分页、固定勾选/缩略图与右操作，全部居中。商品ID从列表移至详情，仍全程字符串并可复制。

前端契约补充（非 Backend DTO）：

- `shopId/shopName` 始终表示请求罗盘的自有店铺；`merchant` 独立保存商品商家平台店铺ID、名称及演示竞品标记。列表店铺名来自 merchant；缺失显示 —。`markCompetitor(merchantShopId)` 只能使用明确商家ID，绝不回退请求店铺UUID；仅演示标记，不启动监控。
- `sourceContext` 提供实际结果上下文：榜单ID/名称、口径键、类目、周期、监控排名范围、检查时间。候选分页响应 `contexts` 基于全部筛选记录，与当前分页无关；页面不写死示例值。Mock 明确给出示例上下文，Real 不加载它。
- `previousRank` 保存上次榜单ID/口径/排名；只有同榜单同口径才比较，排名数字变小表示上升。没有可靠上次记录或本次排名缺失时不显示变化；详情保留不同口径记录并注明不可比较。
- `discovery`（新进入监控范围/已发现/离开监控范围/未知）独立于 `firstListed`（平台首次上榜）；退出监控范围不等同下榜。`firstDiscoveredAt` 与指标获取时间独立保留。
- `collectionStatus` 仅为未采集/已演示采集/演示失败/未知，Mock 不能显示正式采集成功。单条与批量按商品去重，共用规则；更新原候选、不新增副本，保留来源、原始区间。批量成功取消选择，失败保留。
- `sourceUrl` 仅展示已提供的 http(s) 来源链接，禁止猜商品URL、脚本协议或含明文身份的URL；当前正常夹具无可靠链接，按钮不显示。
- `updateCompassMetrics(id)` 仅演示更新原候选的指标获取时间；`candidates()`/刷新列表只读已有内存记录，不能冒充平台更新。Real 的新方法同其他方法一样明确不可用、不发猜测请求。

详情沿用 DetailDrawer 的固定底栏/唯一Body滚动；展示完整标题/图片/价格、ID复制、商品商家与请求店铺、完整类目、榜单/排名/发现、差评率/首次上架/获取时间、采集/屏蔽状态。罗盘视频榜单区保留四项原始区间、所属周期及获取时间，不换算未知金额单位、不加入百应近30天销量/佣金/达人数据。底栏关闭为中性、更新罗盘指标为描边、采集资料为主题主按钮。

复用与最小调整：DataTable/PaginationBar/ManagementListSection/TableToolbar/DetailDrawer/ExternalProductImage/ShopSelector/StatusTag 不改公共行为；更多菜单复用 Naive NDropdown。执行选品/保存/批量与详情采集使用已有 primary，刷新/更新/竞品标记使用 secondary。唯一共享能力补充为 AppButton 的可选 `tone="link"`，通过 NButton text + 原 `--text-link/--text-disabled` token，不改变默认 secondary、原 text 或其他调用；不改主题Token/全局颜色。

本轮 Gate 1 实测与四主题1366/宽屏浏览器截图、计算颜色及 Handoff 保存在 `docs/_local/product-selection-candidate-detail-v1/`；以最终 Handoff 的命令结果/精确Candidate为准。唯一 Integration Electron、用户新增视觉确认由 ca97 完成，浏览器不替代该门禁。真实商品请求/商家识别、持久化采集与策略、榜单监控、竞品监控、手机接口、百应及正式达人Session仍待接入；本轮未调用真实平台、数据库或生成接口。

### 候选池/详情/按钮 Gate 1 实测

执行目录 `frontend`；Feature 浏览器固定 `127.0.0.1:4176 --strictPort`，未启动第二个 Electron、Backend 或数据库。

| 命令 | 实际结果 |
| --- | --- |
| `pnpm lint`、`pnpm typecheck` | PASS；Real build 再执行 typecheck |
| `pnpm test` | 133文件 / 550项 PASS，73.09s |
| `pnpm exec vitest run src/features/product-selection src/shared/ui/AppButton.spec.ts src/shared/components/DataTable.spec.ts` | 最终7文件 / 36项 PASS，8.38s；含商家身份、同口径排名、新进入独立语义、原记录保留、短视频不需达人、链接显式选择与默认行为保护 |
| `PLAYWRIGHT_FRONTEND_PORT=4176 pnpm exec playwright test --project=mock e2e/product-center.spec.ts e2e/product-selection.spec.ts --workers=1` | 最终9项 PASS，1.7m；四主题实际颜色/截图、列表与详情、原排序分页/批量部分失败/日期草稿/history/守卫回归 |
| `PLAYWRIGHT_FRONTEND_PORT=4176 pnpm exec playwright test --config playwright.selection-real.config.ts --workers=1` | 1项 PASS，4.9s；仅拦截既有身份/团队/权限，不加载Mock、不请求未登记选品接口，撤权守卫拒绝 |
| `PLAYWRIGHT_FRONTEND_PORT=4176 pnpm exec playwright test --project=mock e2e/disabled-primary.spec.ts --workers=1 --trace=on` | 最终8项 PASS，24.5s；四主题共享启用/禁用文字与图标、hover/focus/loading、即时/批量仅本地Mock，所有API/外部请求均拦截 |
| `pnpm build` | PASS，Real production；无选品Mock handler chunk、商品照片及商家/榜单夹具，既有大chunk告警保留 |
| `git diff --check` | PASS |

共享按钮首次补跑出现3项生图用例在“素材/提示词准备后仍禁用”的断言处超时；原测试与业务代码未修改，带trace的定向4项及完整8项复跑均通过。初次失败证据保留于 `shared-buttons/`，原因未确定，不宣称修复了AI业务问题。原单测jsdom XHR stderr、Playwright颜色环境告警及构建大chunk告警如实保留。

四主题已检查1366×768候选/详情与正常/禁用/链接计算颜色，宽屏回归沿用1920×1080。列表需要横向滚动以容纳独立字段，不压缩公共行高，分页固定在卡片底部；详情Body独立滚动、底栏常驻。截图来自代码实际浏览器渲染，均为Mock或明确Real不可用，不是Electron验收。真实Integration Electron和用户本轮视觉复验仍待ca97，不运行生产或正式平台调用。

## 紧凑列表与详情首屏返修（接续b30eb93，2026-10-09）

本节覆盖此前80px列表图、全列居中、单项更多菜单和常驻日期说明，其他有效功能保留。

- Mock只在选品库切换栏旁显示一个“演示数据”标识；不在日期字段下反复写Mock。四项AppRadio旁的NTooltip展示service返回的完整示例区间，保存仍只有相对周期。瞬时操作回执继续明确演示边界，不能把演示采集改叫真实成功。
- 列顺序与上一轮一致。列表56×56px图片（等比）、主题`--space-3`上下留白，实测行高81px；详情摘要仍为原80px图片。标题240、商家150、末级类目120，三列左对齐并保留Ellipsis/Tooltip；ID仍只在详情、完整类目路径不修改。其他列居中；选择44/图片80左固定、操作220右固定，完整宽度1634，窄窗口局部横向滚动。
- 范围摘要由`CandidateSourceContext`的榜单名、`periodLabel`、排名上下限生成；NPopover“查看范围”保留完整日期、类目、排名与检查时间。上下文来自完整筛选结果，不写死页面文字、不改真实统计口径。
- 排名同口径才比较；`↑ 2`复用NText success、`↓ 2`复用error、同值“持平”，无可靠历史不显示变化。发现情况缩为“新进入/已发现/已离开”，NTooltip解释监控范围含义；不等同平台首次上榜或下榜。
- 行内直接提供主题链接“详情”、small描边“采集资料”、普通文字“屏蔽/恢复”，12px间距、垂直居中、nowrap。删除单项NDropdown，屏蔽/恢复与批量仍使用原service和互斥/逐项回执。
- 详情依次为摘要→罗盘视频榜单数据→排名与发现→商品基础信息→请求来源。视频区两列四项、原始区间与缺失不变，周期紧邻标题、获取时间为辅助；两个视口均能在首屏看到四项。商家平台ID与请求店铺UUID继续分离。底栏关闭/更新罗盘指标/采集资料及Body滚动保持。
- 共享调整仅`AppButton.size`（默认medium，可选small）与`DataTable.themeOverrides`透传已有AppTable能力（默认undefined）；不改全局token、表格CSS、按钮默认tone、权限、接口或Electron。

### 本轮Gate 1验证

运行位置81a1，浏览器`http://127.0.0.1:4176 --strictPort`；实际Mock服务加载返修工作树。不是旧b30窗口，不是Electron证据。

| 命令（frontend） | 结果 |
| --- | --- |
| `pnpm run lint`、`pnpm run typecheck` | PASS；最终build再次执行typecheck |
| `pnpm run test` | 133文件/553项PASS；最后样式作用域与无用导入修正后另复跑定向 |
| `pnpm exec vitest run src/features/product-selection src/shared/ui/AppButton.spec.ts src/shared/components/DataTable.spec.ts` | 最终7文件/39项PASS；含语义排名/类目末级、排列、可选共享属性、详情顺序/两列/缺值、原批量/草稿/竞态 |
| `PLAYWRIGHT_FRONTEND_PORT=4176 pnpm run test:e2e:mock e2e/product-center.spec.ts e2e/product-selection.spec.ts e2e/disabled-primary.spec.ts --workers=1 --trace=retain-on-failure` | 最终17项PASS，2.5m；四主题1440×900/1366×768同夹具/100%缩放，真实56px照片、81px行/12px间距、固定列/排序分页、首屏四项、日期Tooltip/保值、商家区分及共享按钮8项；生图仅Mock且所有API/外部请求拦截 |
| `PLAYWRIGHT_FRONTEND_PORT=4176 pnpm exec playwright test --config playwright.selection-real.config.ts --workers=1` | 1项PASS；无演示标识/Mock handler/猜测选品请求，普通成员撤权后守卫仍拒绝 |
| `pnpm run build` | 最终PASS；Real产物没有选品Mock handler、商品照片或夹具；保留原大chunk告警 |
| `git diff --check` | PASS；以最终Handoff记录为准 |

迭代证据保留：首次浏览器运行长标题Tooltip挡测试目标、日期旧DOM定位超时，以及h渲染节点未命中scoped操作间距；已分别修正测试移出/关闭提示、删除旧定位、将业务容器作用域定向deep到动作节点并复验。未修改公共表格样式。截图等待图片加载及动画完成，避免把加载帧当正常照片；完整单测既有jsdom XHR stderr、Playwright颜色环境和构建大chunk告警不作零告警声明。

实际截图/计算布局/前后索引、精确Candidate与正式Handoff在`docs/_local/product-selection-compact-repair/`（本机忽略，不进Git）。本阶段无Backend/DB/Migration/真实平台调用，不需要重测经营数据。
ca97须把新Candidate实际加载到唯一5180 Mock Electron，记录Renderer尺寸/缩放并让用户集中复验列表、详情、日期区域；当前用户窗口尺寸尚未取得，不能用浏览器尺寸代替。Real边界另验，未完成Electron不标视觉PASS。

真实最小闭环尚未实施。仅先核对正式DouyinApiClient/ShopSession权限路径与既有basic_info脱敏材料；生产只读证据由ca97统一协调，basic_info字段存在不是榜单成功或非零差评率单位已确认。前端确认后再冻结榜单/基础信息契约、安排DB/Slot及真实平台→入库→API→Real页面验证。百应、达人登录、监控、手机、自动上架仍不纳入，商品资料按钮不能报真实手机采集成功。

## 候选池与详情视觉收口（接续72fb71cf，2026-10-09）

本节覆盖上一节的列表范围摘要/查看范围、正文三列左对齐和详情常驻解释，其他已验证成果保留。状态仍为 UI_ONLY，无 Backend、数据库、Migration、平台请求、手机或全局主题变更。

- 列表移除范围摘要与入口，来源事实仍保存在原契约和详情中。无勾选时不显示数量；有勾选时仅“已选 X 项”。Naive 原生全选继续只选当前页，现有 NTooltip 只在原全选控件悬停/聚焦时提示。统一“演示数据”标识和演示操作回执不变。
- 全部表头/内容居中；标题两行 NEllipsis，商家与末级类目单行 NEllipsis，内部容器也居中，溢出提示保留全文。全部单元格局部采用 `--space-3` 四边12px，图片56px，正常行高约81px；不改公共表格默认样式。
- 列宽依次为选择44、图片80、标题弹性（最小240）、店铺150、类目120、排名100、发现100、价格120、差评率100、首次上架140、状态120、操作220。固定列合计1294，最小表宽1534；标题为唯一未指定固定 width 的列，宽屏剩余宽度只交给标题。选择/图片左固定、操作右固定，操作12px间距、居中、不换行；窄窗口局部横向滚动。
- 原生 sortable 表头仍使用原排序状态与箭头。Naive 的 align 只控制文字，内部标题默认 flex:1 会把箭头推到右边；通过本页列 className 与两条局部布局规则居中文字/箭头整体，不修改图标、排序算法或全局样式。原生选择列默认padding为0，本页列 className 仅同步为12px。没有新增公共控件。
- 详情保持摘要→罗盘视频数据→排名与发现→商品基础信息→数据来源。前三个数据区共用 bordered NDescriptions 的主题边框/圆角/标签底色和12px内边距；视频、排名区各两列。周期只显示相对名称，完整区间在Tooltip和折叠来源内；指标获取时间只出现一次。底部数据来源默认折叠、换商品/重开恢复折叠，保留取数自有店铺、来源、完整区间、类目与监控范围、检查时间。
- 不可比较、金额单位未确认改为字段Tooltip；原判断不变，不显示不可靠涨跌、不换算未知单位、不填零。商家身份缺失的必要反馈、错误及批量部分失败仍保留。请求自有店铺与商品商家不混淆。
- 跨AI导航对照测试原来未指定 `visualMock=1`；ca97的5180/8100复现trace记录AI配置API返回401 `HUMAN_AUTHENTICATION_REQUIRED`、页面跳到登录，并非已证明切换栏样式不同。此次仅让Mock UI对照使用已有隔离视觉夹具，并阻断API/外部请求，断言零API尝试；不改Real认证、守卫或AI业务。Owner修正后的对照测试通过，仍需ca97在精确新候选复跑。

本轮精确Candidate、命令结果、布局测量及四主题实际浏览器截图记录在本机忽略目录 `docs/_local/product-selection-visual-closeout-v1/`。实际预览用4176 strictPort，保留同一数据；1440×900、1366×768和宽屏检查属于浏览器证据，不替代当前用户窗口或Electron。
Owner当前浏览器/原生工具初始化报“failed to write kernel assets / 系统找不到指定的路径 (os error 3)”，未取得用户实际Renderer尺寸/zoom；不通过另一个低层入口绕过。Gate 1后ca97更新5180候选快照、核对实际加载SHA，并在唯一Integration Electron集中补验。旧72fb或本轮浏览器PASS不能替代新增视觉验收；跨AI导航须在集成端精确新候选复跑，未完成不标Gate 2全部通过。

### 视觉收口 Gate 1 实测

| 命令（81a1/frontend） | 实际结果 |
| --- | --- |
| `pnpm run lint`、`pnpm run typecheck` | 最终PASS；Real build另执行typecheck |
| `pnpm run test` | 133文件/553项PASS，86.78s；既有jsdom XHR stderr保留 |
| `PLAYWRIGHT_FRONTEND_PORT=4176 PLAYWRIGHT_API_MODE=mock pnpm exec playwright test e2e/product-selection.spec.ts e2e/product-center.spec.ts e2e/disabled-primary.spec.ts --project=mock --config ../.codex/product-selection-visual-closeout/playwright.mock.config.ts --workers=1 --trace=retain-on-failure` | 17项PASS，2.7m；复用已核对的Feature Mock Vite，未新增Electron/Backend。含排序/分页、当前页全选Tooltip/聚焦、批量部分失败、长内容居中/两行、省略提示、四主题、原日期/策略/竞态及共享按钮 |
| 同配置，`e2e/product-selection.spec.ts --grep 'candidate pool: four themes\|centered candidate columns'` | 修正实际滚动节点后2项PASS，55.9s；四主题1440×900/1366×768，表头箭头整体居中/12px padding/81px行、三块边框一致/来源默认折叠、真实横向滚动与左右固定列、2240宽屏只有标题扩展 |
| `PLAYWRIGHT_FRONTEND_PORT=4176 pnpm exec playwright test --config playwright.selection-real.config.ts --workers=1 --trace=retain-on-failure` | 1项PASS，5.6s；Real不加载Mock/不发猜测请求，普通成员撤权后守卫拒绝。仅身份/团队/权限拦截，无真实Backend/DB |
| `pnpm run build` | 最终PASS，Real production，22.00s；扫描未发现选品Mock handler/商品照片/商家夹具，原大chunk告警保留 |
| `git diff --check` | PASS |

用户另提供真实Electron修改前截图（2552×1375图片像素）：仍可见旧范围摘要/查看范围/零选中说明，不能当作新候选验收。截图像素不等于已确认Renderer视口或缩放。已保留本机对照；实际新版加载和操作仍交ca97。

收尾校验发现旧滚动测试操作的是NScrollbar外层，而非内部`.n-scrollbar-container`；此前“右滚动”截图未产生真实移动，不作滚动通过证据。已改为实际滚动节点，并断言scrollLeft大于0、非固定标题移动、图片/操作表头位置不变、排序表头在右滚动后可见；垂直滚动也核对实际scrollTop。新证据保存在`scroll-verified/`，1440视口横移411px且两个固定列位置不变；旧输出保留但明确不采用其滚动结论。没有借测试修正变更业务或公共表格。

## 文字层次与详情顶部时间返修（接续c0e1da78，2026-10-10）

仅调整候选池及候选详情的文字表现、顶部时间信息和定向测试；状态仍为 UI_ONLY。沿用原列宽、居中、12px内边距、56px列表图片、操作排列、两列指标/排名表格与详情分区顺序。不修改全局主题、基础控件、接口、数据源、Backend、数据库、Migration或Electron壳。

### 文字与组件复用

| 内容 | 现有字号/字重 | 现有颜色角色与应用方式 |
| --- | --- | --- |
| 详情商品标题 | `--font-size-page-title` / `--font-weight-semibold`（18px/600） | `--text-primary`，只作用于详情标题 |
| 详情分区标题 | `--font-size-section-title` / `--font-weight-semibold`（16px/600） | `--text-primary`，折叠来源标题同样处理 |
| 罗盘四项原始指标 | 22px / `--font-weight-semibold` | 现有字号token没有22px，唯一一次定义在本Feature的 `.candidate-detail__metric`；NText depth=1，缺失depth=3 |
| 普通字段值/候选池正文 | `--font-size-body` / `--font-weight-regular`（14px/400） | `--text-primary`，局部NDescriptions themeOverrides与NText depth=1；列表未放大字号 |
| 详情字段名称 | `--font-size-secondary` / `--font-weight-regular`（13px/400） | `--text-secondary`，复用NDescriptions原生labelStyle和themeOverrides |
| 周期/指标获取时间 | `--font-size-secondary` / `--font-weight-regular`（13px/400） | NText depth=3，使用原辅助文字色 |

Naive默认Descriptions标签比字段值深，NText未指定depth时为次文字色；此次通过组件支持的**局部**主题映射纠正，不覆盖Naive内部全局颜色、不改变其他模块。缺值为辅助色，真实0为正常主文字；排名涨跌仍走success/error，链接及按钮沿用当前主题色。StatusTag保留其现有状态语义。

### 顶部时间与来源语义

- 摘要仍为左图右内容；商品标题与紧凑信息使用可换行的flex容器。短标题有空间时同行，长标题/窄抽屉自然换行，不缩字号、不增宽抽屉，不产生横向滚动；价格仍在下一行。
- 紧凑信息为“罗盘：{sourceContext.periodLabel} · 更新 {metricsRetrievedAt}”。复用原dayjs `formatCandidateTime`，可传 `MM-DD HH:mm` 输出；原其他调用默认 `YYYY-MM-DD HH:mm` 不变。
- NTooltip展示 `sourceContext.statisticalPeriod` 完整统计区间，以及 `metricsRetrievedAt` 完整获取时间。周期/获取时间缺失均显示 —，不得用榜单检查时间、首次发现时间或当前时间补值。
- 罗盘视频数据区仅保留分区标题及紧接的四项表格，不再放常驻周期或单独获取时间。原始区间如 `1万–5万` 原样显示，未知单位只在Tooltip提示，不估算或换算。
- 默认折叠的数据来源保留完整统计区间，将“检查时间”明确为“榜单检查时间”，仍只读 `sourceContext.checkedAt`。两类时间相互独立，首次发现/平台首次上榜/首次上架语义不变。

实际浏览器截图、四主题计算字号/颜色、长标题/420px窄抽屉、缺失时间/真实0测试及精确Candidate/Handoff保存在本机忽略目录 `docs/_local/product-selection-typography-v1/`。浏览器4176与唯一Integration Electron5180证据分别记录；Gate 1后由ca97更新同一候选快照并核实实际加载SHA，不以旧窗口或浏览器截图宣称本轮Electron视觉通过。本轮交付至新预览与视觉验收，不追加业务或发布。

### 文字返修 Gate 1 实测

| 命令（81a1/frontend） | 实际结果 |
| --- | --- |
| `pnpm run lint`、`pnpm run typecheck`、受影响文件 `prettier --check` | 最终PASS |
| `pnpm run test` | 最终133文件/555项PASS，76.16s；既有jsdom XHR stderr保留 |
| `pnpm exec vitest run src/features/product-selection src/shared/ui/AppButton.spec.ts src/shared/components/DataTable.spec.ts` | 最终7文件/41项PASS，10.36s；含顶部格式/缺失时间不回退、0与null、原批量/日期/多渠道/权限边界相关回归 |
| `PLAYWRIGHT_FRONTEND_PORT=4176 PLAYWRIGHT_API_MODE=mock pnpm exec playwright test e2e/product-selection.spec.ts e2e/product-center.spec.ts e2e/disabled-primary.spec.ts --project=mock --config ../.codex/product-selection-visual-closeout/playwright.mock.config.ts --workers=1 --trace=retain-on-failure` | 最终19项PASS，3.1m；四主题实际计算字号/字重/颜色及截图、1440×900/1366×768、420px窄抽屉、长标题/短标题同行、Tooltip完整区间/时间、真实0/缺失与未知状态，原居中/列宽/固定/滚动/排序/分页/批量/导航/共享按钮不回归 |
| `PLAYWRIGHT_FRONTEND_PORT=4176 PLAYWRIGHT_API_MODE=real pnpm exec playwright test --config playwright.selection-real.config.ts --workers=1 --trace=retain-on-failure` | 1项PASS，10.1s；只拦截既有身份/团队/权限，Real不加载Mock或调用猜测选品接口，普通成员撤权守卫仍拒绝 |
| `pnpm run build`、`git diff --check` | 最终PASS，Real production，19.00s；未输出选品Mock handler/商品照片/商家及指标夹具，原大chunk告警保留 |

首次新时间断言发现Feature Vite缓存旧TS格式化函数，组件已新但函数仍旧；已核对进程并重启**本Worktree的4176**，实际响应确认使用可选格式参数，再完成全部回归。另两次测试在抽屉/主题过渡帧读取位置或颜色，已等现有有限动画结束后测量，不改业务动画、不加性能重构。初次失败材料保留，最终证据使用`final-regression/`、`real-boundary/`；四主题截图/计算值为实际浏览器Mock渲染，不能代替唯一Electron或用户视觉验收。Integration更新后仍需核对实际加载精确SHA及新时间格式，不能仅依据Git HEAD或HMR宣称完成。

## 审核返修与无用残留清理（接续c44687ed，2026-10-10）

- 编辑已保存策略的抽屉“立即获取”复用既有 `retrieve(draft, strategyId)`；成功仅发送 `retrieved` 事件，由 StrategyList 的现有 TanStack Query refetch 更新最近结果。保存仍是独立动作，未提交草稿不写入策略，新建获取不自动创建策略；获取失败不发成功刷新事件。
- 外部商品图不再强制 `crossorigin=anonymous`。正常显示和 NImage 预览使用浏览器原生图片请求，仍保留 lazy、no-referrer、缺图占位及失败重试；没有接入系统认证 HTTP Client、图片代理或下载缓存。
- 删除商品顶层重复的 `statisticalPeriod`、列表 `contexts` 汇总和计算；详情仍消费 `sourceContext.statisticalPeriod`，榜单检查与指标获取时间继续来自两个独立字段。导航只删未被 ContextSwitchBar 消费的旧 description，采集任务/Real 的未接入空态保留。
- 策略列表删除无操作消费者的选择列、checked 状态/绑定及翻页清选；不添加批量功能。已有策略名左固定、操作右固定、分页/搜索/编辑保持，scroll-x 仅减去删除的44px选择槽。
- 用户补充的操作间距问题：候选池“屏蔽/恢复” quaternary 按钮原有左右 padding 使12px容器间距看起来不对称。仅为该按钮传入 Naive 支持的 `paddingSmall: '0'` 局部主题覆盖，按钮类型、颜色、悬停/焦点、容器12px gap、220px操作列及其他AppButton调用不变。实际回归测量“详情文字→采集资料边框”和“采集资料边框→屏蔽文字”两侧可见距离，不只断言容器gap。

本轮仍为前端/Mock、UI_ONLY，无 Backend/业务API/数据库/Migration/平台请求/手机或Electron变更。准确Candidate、定向检查、实际浏览器截图与Handoff记录于忽略目录 `docs/_local/product-selection-review-v1/`；交ca97更新同一5180候选快照并保留登录，浏览器证据不代替唯一Integration Electron验收。本任务不含生产发布。

### 审核返修 Gate 1 实测

| 命令（81a1/frontend） | 实际结果 |
| --- | --- |
| `pnpm run lint`、`pnpm run typecheck`、受影响文件 `prettier --check` | PASS；测试定位修正后再执行lint/格式检查 |
| `pnpm run test` | 133文件/558项PASS，85.30s；既有jsdom XHR AggregateError stderr保留 |
| `pnpm exec vitest run src/features/product-selection src/shared/ui/AppButton.spec.ts src/shared/components/DataTable.spec.ts` | 7文件/44项PASS，16.97s；增加已有策略ID/草稿不保存、新草稿不创建、获取失败不发成功刷新事件 |
| `PLAYWRIGHT_FRONTEND_PORT=4176 PLAYWRIGHT_API_MODE=mock pnpm exec playwright test e2e/product-selection.spec.ts e2e/product-center.spec.ts e2e/disabled-primary.spec.ts --project=mock --config ../.codex/product-selection-visual-closeout/playwright.mock.config.ts --workers=1 --trace=retain-on-failure` | 最终21项PASS，3.2m；已有策略抽屉获取后列表最近结果更新，取消重开条件未保存、新建获取后仍2条策略；两个不同测试源没有ACAO头，实际缩略图/预览naturalWidth有效、404显式重试后恢复，图片不附中控认证/团队/Referer；原候选/详情/时间/四主题/导航/共享按钮回归通过 |
| 同Mock配置，`--grep 'centered candidate columns'` | 四主题、1440×900和1366×768实际测量两侧可见操作间距均12px，整体居中/nowrap、正常行高81px；不只断言CSS gap |
| `PLAYWRIGHT_FRONTEND_PORT=4176 PLAYWRIGHT_API_MODE=real pnpm exec playwright test --config playwright.selection-real.config.ts --workers=1 --trace=retain-on-failure` | 1项PASS，5.4s；Real无Mock回退/猜测选品请求，团队撤权后守卫仍拒绝；只拦截已有身份/团队/权限API |
| `pnpm run build`、`git diff --check` | PASS；Real production build 21.07s，产物无选品Mock handler/商品WebP/商家和指标夹具；既有大chunk告警保留 |

初次新增E2E失败为测试假设：原生radio输入被其可见标签覆盖，已改为点击标签并断言选中；非可信HTTP测试源未提供预设Fetch Metadata头，已改为核对实际图片请求、无Origin/认证/Referer及无ACAO响应下的缩略图/预览加载结果。初次失败材料保留于 `focused/`，修正后两个新增交互在 `focused-2/` 通过，全部最终回归使用 `mock-regression/`。未修改业务条件、Mock延迟或公共控件绕过测试。

## 候选池图片与列宽尺寸收尾（接续91461d4a，2026-10-10）

本轮仅调整候选池图片、内边距、列宽及相关定向测试。保留此前策略获取/查询刷新、图片无CORS展示/失败重试、残留清理、字体/四主题及所有业务交互；仍为 UI_ONLY，无公共表格API、全局Token、Backend、数据库、Migration、平台或Electron变更，不发布生产。

- `ExternalProductImage` 仅将 thumbnail 由56px改为64px；summary仍为80px。继续object-fit:contain、NImage点击预览、lazy/no-referrer及显式失败重试，不裁切或拉伸。
- 候选池局部 `tdPaddingMedium` / `thPaddingMedium` 统一消费 `--space-2` / `--space-3`（上下8px、左右12px）。现有原生selection列覆盖改为消费同一`--n-td-padding`，不叠加新规则。图片与padding自然形成约81px行；没有固定行高、内容裁切或公共默认密度变更。表头实际约39.4px、垂直居中。
- 基础列宽按字段顺序为44/88/280/140/100/88/88/112/96/140/100/220，总宽1496px，`scroll-x`同步1496。选择/图片左固定、操作右固定；窄窗口正常横向滚动，不压缩功能列。
- 使用已安装VueUse `useElementSize`读取本页DataTable容器，并通过已有列width配置分配宽屏余量：标题优先取一半余量、最多增加80px（280–360px）；余下按店铺/类目6:4分配。其他九列宽度稳定，不扩展公共表格API或另建布局框架。全部省略容器继续居中、标题最多两行并可悬浮看全文。
- 操作容器仍为12px gap、居中nowrap，屏蔽/恢复按钮原有局部padding修复保留；两侧可见间隔均12px。详情字号、四项原始指标、80px摘要图、周期/指标获取时间和独立榜单检查时间均未改变。

本轮1440×900、1920×1080完整列表及四主题/实际横向滚动/布局测量记录于忽略目录 `docs/_local/product-selection-sizing-v1/`，等待全部10张照片加载后截图。浏览器Mock证据不替代唯一Integration Electron；Gate 1后交ca97更新同一5180候选快照、核对精确SHA并保留登录，不新增验收窗口。首轮2240额外宽屏断言在ResizeObserver更新前读取了旧列分配，已改为等待实际宽度重算完成；失败材料保留，不更改业务动画、延迟或功能逻辑。

### 图片与列宽 Gate 1 实测

| 命令（81a1/frontend） | 实际结果 |
| --- | --- |
| `pnpm run lint`、`pnpm run typecheck`、受影响文件 `prettier --check` | PASS；尺寸监听通过现有DataTable根HTMLElement读取，不扩展组件API |
| `pnpm exec vitest run src/features/product-selection src/shared/components/DataTable.spec.ts` | 6文件/41项PASS，10.09s；覆盖指定基础宽度/scroll-x、局部padding、原策略/详情/批量/日期/缺值回归 |
| `PLAYWRIGHT_FRONTEND_PORT=4176 PLAYWRIGHT_API_MODE=mock pnpm exec playwright test e2e/product-selection.spec.ts e2e/product-center.spec.ts --project=mock --config ../.codex/product-selection-visual-closeout/playwright.mock.config.ts --workers=1 --trace=retain-on-failure --output=../docs/_local/product-selection-sizing-v1/verified-regression` | 最终13项PASS，2.9m；1440×900及1920×1080四主题整页、64px缩略图/80px摘要图、全部10图实际加载、标题两行居中、8/12px内边距、12px可见操作间距、横向滚动固定列、排序/分页/批量、跨AI共享导航、图片无CORS与失败重试等相关回归 |
| `pnpm run build`、`git diff --check` | PASS；Real production build 18.89s，产物未包含选品Mock handler/商品照片/商家指标夹具；原大chunk告警保留 |

全部主题实测正常行高81px、表头39.390625px、操作左右可见间隔12px。1440视口表格可视宽1123px，12列保持1496px基础总宽并横向滚动373px；1920视口可视宽1603px，标题/店铺/类目334/172/121px，其余九列不变，无横向溢出。额外2240压力检查标题上限360px成立。

首轮typecheck暴露VueUse的VueInstance与DataTable类型化emit不兼容；改为读取已有根HTMLElement后lint/typecheck、定向unit及全部13项E2E重新通过。未调整业务接口、Mock延迟、动画或全局表格。最终截图来自 `verified-regression/`、浏览器Mock、CSS缩放100%；真实Electron新增影响及用户视觉确认由ca97接续，不能据此宣布Gate 2或生产通过。本轮按尺寸改动范围执行定向验证，未重复后端/数据库/平台或无关全量测试；Real运行态边界沿用91461d4a记录，当前Real构建再核验不含Mock。

## 近7天有限回退与Real手动入口 2026年10月11日

接续58d4a8，ca97已技术审核用户批准的主/备窗口规则。Real选品策略区域保留已确认的StrategyList与StrategyDrawer结构，复用ShopSelector、CategorySelector、AppRadio、现有按钮及Query刷新。后端当前只实现手动获取，不等于删除策略管理或定时配置界面。支持当前授权抖店真实行业/非0有序类目路径、短视频近7天、不限品牌价格、首次上榜关闭、第1–20名。其余取数选择禁用；不把Mock示例日期写进正式POST。

正式POST `/api/v1/product-selection/runs`只发送用户条件及submission_key；服务器在首次接受时按上海日期冻结截至昨日7天/提前一天的备用7天。页面同一草稿提交响应不确定时复用key，不自动重复提交；已接收则读取运行状态。执行开关关闭时明确不可用，数据库结果仍可读。刷新/轮询/候选详情不发平台请求；真实类目GET是明确的店铺平台读操作，不回退Mock。

Real类目显示树保留完整行业/类目路径，但正式提交不包含外层行业ID。多行业树仅当前响应`industry_id`对应分支建立`requestScope`；其他行业及行业根本身不可提交。有真实`requestScope`的非0父级提供“全部”，选择后复用该父级有序路径，不要求继续选四级。UI生成的`/*`仅用于显示选项，立即规范化为父级显示路径，正式service只提交树中核验的实际平台ID；平台0节点仍不作为可提交ID。以显示路径`7/1000009092/1000009142`为例，POST发送行业7及两项类目ID，后端在同一授权店铺的实际树中验证；不硬编码该示例、不静默把未支持的行业映射成7。已有失败run与冻结日期保持原样，修正后的新提交另行验收。

run摘要显示明确日期。除成功空榜外，用户同日明确批准：仅首选第一页精确621000704且未写入事实时，补查已冻结备用一次；该码不通用定性为日期未就绪。备用有数据时显示“已回退一天”；两个窗口都成功空时记录首选区间与“两个窗口均已检查为空”；首选业务拒绝后备用成功空只显示备用实际日期及“备用窗口为空”。补查中/失败区分“首查为空”和“首查被平台拒绝（621000704）”，失败不继续重试；进程中断不显示仍在补查。候选source_context.date_selection镜像Backend正式安全契约，保留fallback_reason及必要的primary_error，actual business/period/hash保持一致；详情顶部保留实际统计区间及回退标识，原检查时间与指标获取时间不混用。旧v1/v2来源仍可读，不给旧数据补造业务拒绝证据。

四主题、字号、1496px基础列宽、64px缩略图、8/12px局部padding、12px操作间距及原Mock交互保留。资料采集、屏蔽、竞品标记、策略保存、调度、百应、正式达人Session仍未接入，不能随手动入口宣称完成。全Feature保持PARTIAL，直到本候选真实入库/API/Real与唯一Integration Electron通过；浏览器拦截测试不替代该证据。

### 已确认策略界面恢复（2026-10-11）

恢复依据为`06bd03c0fa61b00251063e21350cd0cc5445afe5`及其已有截图。本次在`8e47c28b4754cc57f8066adddacf2b5d9308166b`之后追加返修，不回滚分支或数据库：

- `SelectionWorkspace`在Mock和Real均显示原StrategyList；删除替换整页的ManualSelection及`manualOnly`隐藏分支。原列表列配置、工具栏、搜索、分页和右抽屉保持；Real策略数据尚未接入，显示明确不可用状态，不生成演示策略行。
- 抽屉恢复策略名称、共用达人入口、纵向渠道、全策略定时/状态及原保存底栏。Real保存与启用不可用；定时规则可在草稿中查看/编辑，但明确待接入，不创建或启用计划。手动提交仅使用店铺及取数条件，不保存名称、状态或定时草稿，不因草稿元信息变化重置未确定回执的submission_key。
- 正式“立即获取”留在原抽屉；最近run及安全失败反馈放在原列表区，沿用Query刷新和活动run轮询。不以执行结果页取代策略管理，不增加策略CRUD或调度接口。
- CategorySelector复用NCascader支持的placement、menuProps和menuHeight；本轮体验收口采用左下优先及Naive自带边界翻转，限定视口宽高，保留原生列滚动及必要的横向滚动。使用现有间距/弹层主题Token，不扩展基础控件或全局主题。

Signer、实际发送Cookie签名、主/备日期冻结及有限回退、run、候选/来源持久化、正式API和Team/Shop权限保留，已应用0042/0043不变。界面恢复阶段暂停追加平台请求，其本身不证明真实获取成功。四主题和不同视口的浏览器拦截证据、06bd03c差异清单及实际命令保存在本机忽略目录`docs/_local/product-selection-strategy-restoration-v1/`。ca97已将389030a加载到唯一Real Integration Electron，用户随后确认原界面恢复正常；人工确认与原生截图/坐标操作受限分别登记，不伪造窗口量测。本轮保持该已确认界面，仅补必要日期/安全结果状态，不重复整套视觉确认；完整真实闭环仍须新候选正式执行及Gate 2证据，不能提前发布。

## 选品体验收口 2026年10月11日

从精确Green a9931a8接续，不重做已确认的StrategyList/Drawer和64px缩略图、1496px基础列宽、8/12px局部padding。
保留原策略名称、列表/工具栏、定时/状态区域、保存入口及Real不可用边界；不增加策略CRUD或调度。

- 候选池和策略列表不再常驻最近获取完成横幅。只有当前Actor上下文中主动提交的run注册消失消息：
  通过已有 `GET /runs/{id}` Query轮询，success/partial/failed/interrupted分别使用既有useMessage。
  终态只通知一次；列表刷新、历史latest读取和重进页面不重播历史消息，不删数据库run。
  本次run跟踪归属SelectionWorkspace，切换候选池/策略/采集任务不丢完成提示；Actor/Team切换或离开选品页清理。
  排队/运行仍限制重复操作，真正的查询错误和批量失败提示保留，日期与来源在详情可查。
- `metric-display.ts`统一两个原始端点的显示：100000–250000为10万–25万，
  10000–25000为1万–2.5万，250–500不变；已确认price单位先÷100转元再显示¥万/亿。
  单位不明/混合时保留原端点，无估算中点。金额证据与周期差异见Backend24。
- unit=4差评率在列表/详情共用现有两位百分比格式：0.00067114…为0.07%，0为0.00%，
  缺失/未知单位为—。DTO/数据库保留全部raw/unit精度；不再常驻开发用长小数/单位说明。
- 类目复用TanStack Query，key包含当前Actor/Team上下文和请求shop_id；staleTime/gcTime均24小时。
  切店清除旧选择，回来或重开复用缓存，旧请求不覆盖新店。
  现有抽屉类目旁提供轻量“刷新类目”，仅显式刷新发送refresh=true；失败保留错误/重试。
  提交使用该查询的当前店铺树解析真实路径，删除无期限service Map；后端仍用当前权限与共享缓存核验实际树，前端不是权限依据。
- NCascader bottom-start左下优先，复用其VFollower默认flip和resize/scroll同步，
  配合原视口maxWidth、横向滚动及主题menuHeight；不自写定位算法。
  父级“全部”仍规范化为已存在的真实父级路径，不发送0、/*或伪造ID。

本轮浏览器拦截仅证明前端行为与边界，PostgreSQL使用合成平台证明缓存/权限/提交共享，
不作为新平台实测。ca97须更新新Candidate的5180前端及8100后端，在同一Real Electron核验实际运行版本、
指标、调用次数及普通/最大化菜单；旧41e不作为五项新修复验收。没有Electron主进程变化，无需新桌面包。

## 正式只读绑定（2026-10-10，PARTIAL，历史阶段）

`api/selection-read-api.ts` 镜像正式 `SelectionObservationRead` 和canonical运行摘要，只经既有httpClient调用已登记 `GET /api/v1/product-selection/candidates`、`/observations/{id}`、`/runs`。Actor/Team切换仍由Vue Query查询key隔离；列表刷新只查数据库。前端不持有平台Cookie或Signer，不创建空Job。

`selection-real-service.ts` 将数据库返回映射到已验收候选池/详情，不复用Mock handler。候选ID采用observation_id以保持精确来源；19位product_id不转Number；请求Shop与实际商品商家分开，多个商家不冒称唯一身份。原始Decimal区间字符串不缩放、不取中点；差评率独立保留raw/unit，不加百分号或开放排序。日期/类目尚未冻结的快捷映射不推导，保留明确统计区间，榜单检查时间与指标获取时间不互换。基础信息失败显示安全错误且已存候选仍可查询。

Real列表读最近canonical运行，分别显示未获取、排队/运行、合法空成功、失败、partial及interrupted；运行进度刷新不创建提交回执或平台请求。候选查询失败走已有错误态，不伪装为空榜单；旧运行的当前来源关联不是历史商品快照。

Mock原有视觉/筛选/操作保持。Real资料采集、屏蔽、竞品标记、策略保存与定时仍未接入，禁用或返回不可用；不假成功。正式 `GET /categories?shop_id=UUID` 与前端categories service已实现，返回树使用路径限定显示ID以区分多个0/全部节点，并校验响应shop_id，失败不回退Mock；显示路径不直接冒充平台Query。Real策略/手动获取UI仍受Backend映射门禁阻塞，本候选尚未在合法会话下验收真实类目选择与手动闭环。原列宽1496、64px缩略图、局部8/12pxpadding、12px操作间距和四主题不改；完整Electron验收仍由ca97负责。
