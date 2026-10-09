# 选品库前端与 Mock 交互 V1

状态：UI_ONLY；前端契约草案，不是 Backend DTO 或平台接口契约。
Green 基线：`b34e43cb90356e03d2f793c4146c6775a11f5ab3`（ca97 确认精确 CI PASS）。
分支：`feat/product-selection-frontend-v1`。当前前端返修阶段无 Backend、数据库、Migration、Electron 壳、真实平台或调度变更。用户已授权在前端确认后接续真实手动闭环；该阶段须另登记契约、Feature DB/Migration及真实验证，不能用本阶段证据宣称完成。

当前返修以文末“紧凑列表与详情首屏返修”为准，旧候选列宽/80px列表缩略图/全列居中/更多操作菜单与常驻日期说明仅为历史验收记录，不代表当前结构。

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
- retrieve(input, strategyId?)：允许未保存策略；选中的短视频返回演示回执，百应返回 unavailable/count=null。仅选百应明确失败，同时选择时返回部分演示回执；不会把百应计入完成数量。传入已有策略 ID 更新最近演示结果，不是平台采集成功。
- list/get candidates：先完整筛选，再原始日期/差评率排序（null 双向末尾、同值 ID 稳定），再分页。
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
