# 选品库前端与 Mock 交互 V1

状态：UI_ONLY；前端契约草案，不是 Backend DTO 或平台接口契约。
Green 基线：`b34e43cb90356e03d2f793c4146c6775a11f5ab3`（ca97 确认精确 CI PASS）。
分支：`feat/product-selection-frontend-v1`。无 Backend、数据库、Migration、Electron 壳、真实平台或调度变更。

## 实施前复用清单

| 现有路径（frontend/src） | 用途 | 新增边界 |
| --- | --- | --- |
| shared/components/ContextSwitchBar.vue | 保留 framed 三选项和 query 历史 | 不改公共切换组件 |
| shared/components/ManagementListSection.vue、FilterBar.vue、DataTable.vue、PaginationBar.vue | 两种列表、稳定底部分页、固定列、居中 | 仅增加选品业务列定义 |
| shared/components/DetailDrawer.vue | 商品详情 | 仅新增选品指标内容 |
| shared/ui/AppDrawer.vue、AppButton.vue、AppSelect.vue、AppInput.vue、AppNumberInput.vue、AppSwitch.vue | 策略右抽屉、条件与独立保存/立即获取 | 组合已有 footer，不改变 FormDrawer |
| shared/ui/AppCheckbox.vue、AppRadio.vue、AppTimePicker.vue；Naive NCollapse/NCollapseItem | 选择渠道、表单价格模式、每日时间、纵向折叠 | 不用导航条充当表单，不新建折叠/时间控件 |
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
- demo action：屏蔽/恢复仅修改 Mock 池；采集入库仅演示回执，不写正式商品库。
- `collectBatch(candidateIds)`：前端草案，输入为当前勾选候选 ID；按字符串 productId 去重，`results` 每个商品一项，包含 `candidateId/candidateIds/productId/state/message`。同商品多个候选别名共同回填；不存在的候选 productId=null、failed。成功与失败均返回，单项失败不终止其余项。单条与批量使用同一 collect 规则；mode 固定 mock、成功态名 demo，不声称正式入库。
- 批量成功项取消勾选，失败项保留并逐项显示原因；请求级失败保留全部选择，执行中互斥。全选只作用当前页，换页/搜索/筛选/排序清空选择。Real collectBatch 与其他业务能力同样明确不可用，不调用猜测接口。
- 未确定的“更多”日期选项、原始支付金额单位不猜测、不换算。

Real 后续接入须先冻结 Backend/OpenAPI 与授权、达人 Session、平台 Endpoint、单位和调度契约；不能直接把本草案 URL 化。

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
- 日期 AppSelect、价格 AppRadio、每日 AppTimePicker；选项“更多”不产生未知值。两渠道纵向折叠，共用顶部店铺/达人，仅一套启用/定时。
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

未执行项：唯一 Integration Electron 的视觉/操作验收由 ca97 在 Gate 2 完成；真实平台条件匹配、类目 API、达人登录/Session、持久化策略、正式采集/入库、后台定时与手机能力均未接入。未定义的“更多”日期选项、金额单位保留未知。百应条件为空且不生成模拟取数结果。

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
