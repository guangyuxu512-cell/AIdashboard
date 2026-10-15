# 商品数据前端 V1 — Gate 1 / Handoff

本记录保留原05f1d25候选事实。2026-10-15用户提出的标题单行及ID前缀返修，
以 shop-product-data-title-v1-gate1-20261015.md 和最新Feature候选为准；原候选未获人工通过。

Owner 7d55，分支 feat/shop-product-data-frontend-v1，Integration ca97。
功能基线为精确 Green 9bb64ac76bf9e0f51fb1715517cf8c18cef63e22；
正常 no-ff 同步资源治理 7dc8034、8f727fb，未将治理 HEAD 当作新 Green。
候选为包含本记录的 Feature 最终 HEAD，完整 SHA 由交付回执及本地 preview manifest 记录。

Gate 1：PASS（纯前端与契约盘点）；Gate 2：未执行；人工验收：未覆盖；
部署/发布：未执行。停止“待用户验收，禁止发布”。

## 已交付功能

- 数据中心独立商品数据页，与经营看板并列，复用 shop 守卫，无新后端权限码。
- 同一列表容器内的店铺、ID、名称、店内组、售卖/载体、更多筛选、日期、查询/重置。
- 默认核心指标与个人字段选择、排序、恢复默认、保存/刷新恢复，字段偏好按 userId 隔离。
- 固定商品信息单元格，主图/两行标题/字符串ID合并；完整复制与长标题查看，宽表横滚。
- Mock 的全部筛选结果排序后分页，缺失值最后；0、missing、null、invalid 不混淆。
- 店内分组从零创建、重命名、同店批量设置/移出、删除影响确认；删除不删商品指标。
- 保存失败保留弹窗与草稿，读取失败有重试；人员/团队切换使旧页面和迟到响应失效。
- Real 明确未接入，不发猜测商品请求、不加载商品 Mock、不伪造0条或保存成功。
- 提取 ProductImage 并保留原 ExternalProductImage 兼容包装；原候选池布局及调用未改。
- 前端契约18与后端盘点提案25：已有 → 复用 → 扩展 → 新增，以及真实请求/单位缺证据清单。

ShopSelector 最终归81a1独立增强，本页组合既有 Shop selection Query 与 AppSelect，未另造控件。
协调过程中本地技术片段 f9167c13180865b8aa4cc86bee43f5e413949217 已由正常 revert
2c1d8112acccca3afbc9a075b0baef56aabf7b4a 撤销；最终业务树对 ShopSelector/该片段测试/09契约无增量，
提交历史完整保留。该片段不作为共享支持或单独发布候选。

## 验证命令与实际结果

均在7d55独立依赖/缓存执行；Frontend通过显式4177与strictPort运行，没有Backend/DB/Electron进程。

| 验证 | 结果 |
| --- | --- |
| pnpm install --frozen-lockfile --offline --filter @control-center/frontend... | 成功，383包来自既有store，0下载；原锁与依赖定义未改 |
| pnpm --filter @control-center/frontend lint | PASS |
| pnpm --filter @control-center/frontend typecheck | PASS（build也重新执行） |
| pnpm --filter @control-center/frontend test | 最终148文件 / 692测试 PASS |
| product-data + product Entity + 原候选池/详情 + Registry 定向Vitest | 7文件 / 39测试 PASS |
| pnpm --filter @control-center/frontend build | production Real PASS；仅既有大chunk提示，不扩无关拆包 |
| production产物白名单扫描 | 86个JS；本页mock模块/商品/组演示标记匹配0 |
| pnpm --filter @control-center/frontend exec playwright test --config playwright.product-data.config.ts | 3项Mock PASS |
| pnpm --filter @control-center/frontend exec cross-env PRODUCT_DATA_API_MODE=real playwright test --config playwright.product-data.config.ts | 1项Real边界 PASS，Auth/Shop仅测试拦截，0真实后端调用 |
| git diff --check / 范围、忽略、stash检查 | PASS；原共享stash保留，未暂存本机材料 |

Mock浏览器覆盖：完整ID复制/粘贴回读、全量排序跨页、查询/空态、个人字段保存及刷新恢复、
从零分组创建/批量设置/重命名/删除与保留指标、详情、失败重试、1024×768/1440×900/1920×1080、
全字段超宽滚动、字段弹窗顶部/底部和页面无横向溢出。
候选池实际浏览器验证：缩略图64×64、详情80×80、no-referrer；单测另覆盖图片失败重试及src切换。
Unit另覆盖分组跨店原子拒绝、保存失败保留草稿、个人存储失败重试、迟到的旧Context响应、缺失与0。
Real检查：商品数据请求0、商品Mock模块0、按钮禁用、错误态不是空数据、无shop授权直达拒绝。

早期测试发现并处理：多表达式模板事件经格式化后解析失败，改为显式方法；错误态按钮定位改为
公共组件实际名称“重新加载”；弹窗边界在入场动画完成后再做精确检查，没有放宽边界断言。
完整Vitest有jsdom XHR AggregateError stderr输出，进程exit0且692项通过；不把这些合成测试作为真实API证据。

## 本地证据（忽略，不提交）

根路径：C:/Users/Administrator/.codex/worktrees/7d55/中控台/frontend/test-results/。

- product-data-mock/product-data-queries-sorts-e6ae0-pects-complete-product-data/product-data-normal.png
- product-data-mock/product-data-recovers-quer-7b3a3-ary-and-maximized-viewports/product-data-1024.png
- 同目录 product-data-1920.png、product-data-fields-1024.png、product-data-fields-1920.png
- product-data-mock/product-data-keeps-candida-4bfce--shared-ProductImage-facade/candidate-image-compatibility.png
- product-data-real/production-product-data-un-286bf-enforces-Shop-authorization/product-data-real-unavailable.png

已逐一核看主要普通/最大化列表、普通字段弹窗及Real不可用截图。截图均为虚构演示或前端拦截身份，
不含平台Token/Cookie。真实Electron截图/操作尚未覆盖。

## ca97接续与准确验收步骤

Gate 2先审核最终Feature SHA、18/25契约与范围；只接受UI_ONLY边界，不把样本响应当完整平台API。
资源保持7d55唯一4177，无DB/Slot；由ca97准备匹配候选的受控预览与必要原生环境，再集中请用户确认。
浏览器测试不是用户人工确认。原已完成A/B、原真实Electron/Profile与81a1选品Feature不受本任务支配。

建议单次人工检查：

1. 打开受控商品数据预览，确认“数据中心 → 商品数据”与现有字号/主题。
2. 选择“星河服饰旗舰店”、近7天，查询；按曝光人数排序并换页。
3. 字段配置加入点击人数、调整顺序、保存、刷新；开启更多列检查横滚和固定商品信息。
4. 同店分组管理从零创建“出单款”；勾选当前页商品设置分组，重命名、移出/删除，检查商品和指标保留。
5. 详情查看、完整商品ID复制；普通/最大化窗口检查筛选、表格、字段弹窗和分页无遮挡。
6. 如需演示错误恢复，仅Mock开发预览的 productDataPreview=query-error；点击重新加载。
   Real预览仅核对未接入与权限，不作为真实数据验收。

Mock分组只保留工作区内存，页面刷新会复位；个人字段配置保留。单组归属是待确认的最小演示草案。
不要求用户提供UUID、Cookie、测试数据或准备环境。

## 未覆盖、风险与回退

- 真实商品数据URL/方法/参数、金额单位缩放、日期/去重/比例汇总与全量排序能力仍缺证据。
- 后端、数据库、同步、分组持久化、并发控制、定时、监测/Feishu、本轮真实Electron与用户人工验收均未覆盖。
- Migration Slot：无；数据库：无；无Worker/Signer/Backend代码、迁移、生产配置或新增依赖。
- 回退仅按正常Git revert移除本Feature UI/导航并恢复原图片包装；不清字段偏好、Profile、数据库、旧包或历史成果。
- 尚未合dev/main、标Green或发布，无新安装包；后续真实闭环需要独立契约/资源/验收。
