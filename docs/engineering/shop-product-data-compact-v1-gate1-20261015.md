# 商品数据紧凑复用／默认每页20条 — Gate 1 / Handoff

2026-10-16已正常合入ca97核定Green5a18bd0；本记录保留03bd阶段39/19原始证据，
同步后的完整Candidate及增量验证见shop-product-data-green-sync-gate1-20261016.md。

2026-10-15，Owner 7d55；feat/shop-product-data-frontend-v1，功能Green基线
9bb64ac76bf9e0f51fb1715517cf8c18cef63e22。保留b364原成果、b2草稿及全部失败/测试夹具。
Candidate为包含本记录的最终Feature HEAD，完整SHA见最终回执与本地preview manifest。
Gate 1 PASS，仅本页UI_ONLY；ca97 Gate 2、商品数据人工验收未完成，禁止发布。

## 最小范围：已有 → 复用 → 必要接入

已有商品数据查询草稿、筛选、分组、全量排序后分页、个人列显隐/顺序及持久化保持。
复用81a1唯一权威的ProductInfoCell/ProductImage、ListDensity显式局部主题和AppTable主题细竖线，
不复制组件、不代改共享层、不整合选品0046业务、候选池页面或占位商品库。

本页必要接入：

- 列表/筛选/工具栏/分页显式compact：正文/表头/ID/控件文字12px，标签沿既有13px，
  控件/复制槽28px、缩略图48px、卡片padding12px、组合gap8px。自然65px行，不固定裁内容。
- 商品信息列使用本页304px预算，既有数据列按实际容器分配剩余宽度；保留原字段、排序、
  固定列及对齐，不照搬候选池340–360px，也不把宽屏余量用于拉长标题。
- ProductInfoCell保持单行标题/完整提示、独立ID：行、原字符串复制/固定槽；缺ID保护沿共享实现。
- 详情、分组管理、批量分组、字段配置VNode置于局部主题边界外，不只换Teleport目标。
  弹窗内部仍14px/34px；商品数据详情图64px、ID13px/复制30px，不改为48或80。
- 初次进入默认每页20条，原10/20/50/100选项可切换。改变条数回第一页、清勾选；
  查询/重置/排序保留当前选择。原分页没有存储偏好，不覆盖用户已存选择、不清存储；
  个人字段偏好仍按用户独立存储。其他模块默认分页不改，商品库仍未实现。

无字段/更多筛选语义/日期/实时/API/平台/调度/飞书新增；Backend/DB/Migration/Worker/Electron/
依赖定义均无改动。共享全局竖线来自受审依赖，不扩大为全局密度；字体家族、导航、颜色、圆角不改。

## 正常依赖消费与精确父关系

1. b41dbb6744b3c28f774f595f94ca53b252b9aa19：保留草稿前的本页默认20条独立提交。
2. 6b707c7648e8c9e43494feaa0eba14ab0e4c0df4：正常no-ff纯共享1a8078d，双父：
   b41dbb6744b3c28f774f595f94ca53b252b9aa19 / 1a8078d0cd9917afc11454e84ff0d13d15a1a2f2。
3. b2ccc2f39d4828eeb02641ca27caa00c3d52d7a7：本页接入草稿，明确未过Gate，原Radio失败证据保留。
4. 03d336dee05eb99a21cc0e82193ec001f4ce2e53：正常no-ff消费ca97新交付修补，双父：
   b2ccc2f39d4828eeb02641ca27caa00c3d52d7a7 / 141fec65d413566987c84c79cc172fe4e32216cb。

首次合并的ProductImage/ProductInfoCell/spec add/add采用受审共享完整文件；图片Facade仅注释
冲突、运行字节相同，采用受审版本。Radio修补合并无冲突。当前共享/商品实体/ShopSelector/
图片Facade与141fec65逐字相同，没有7d55独立共享补丁。两个纯共享SHA均不是Green dev。

## 实际验证

消费141fec65后重新执行本轮定向，不重跑无关全套历史：

| 验证 | 实际结果 |
| --- | --- |
| Vitest：商品数据/实体/density/分页/表格，9文件 | 39项PASS |
| Mock浏览器：本页布局、四主题菜单、分页、可选控件、Overlay/跨页、标题、复制、既有流程 | 19项PASS，0失败/skip/flaky |
| 原3视口Radio + 可选筛选Radio探针 | 原4断言全部PASS，14/34变为12/28，未放宽期望或删断言 |
| 四主题实际商品数据Radio及teleport菜单 | graphite/forest/coral/midnight均12px/28px |
| lint / vue-tsc typecheck / 消费后Real生产build | PASS，既有大chunk警告保留 |
| Real产物86个JS资产扫描 | 商品Mock/演示记录/混合ID和共享浏览器Harness标记命中0 |

三视口1024×768、1440×900、1920×1080实测：商品列均304px、图片48×48、行65px，
单行标题不增高；ID文字槽160px/复制槽28px。短2位、18位及98位虚构ID逐个点击复制后，
Chromium实际剪贴板回读完整一致，不含ID：前缀，不做Number转换。隔离140px容器压力用例中，
文字缩到108px，按钮仍28px可见；此压力用例不冒充人工窗口操作。

默认20/切换10及50、第二页返回第一页/清选择、重置保留所选条数、分组创建/更名/批量/删除影响、
排序分页、列配置保存刷新、失败恢复均通过。详情图64/标题14/ID13/复制30、弹窗14/34及离开本页
后店铺页输入14/34恢复默认也通过。全局竖线为原生主题1px，不追加详情描述双线。

原始product-data-compact-v3的14 PASS/5 FAIL、可选控件探针和b2草稿不清理、不改写。
其中1项是旧路由尚未卸载的测试竞态，已在b2修复并单独通过；另外4项才是共享Radio缺口，
本轮消费修补后独立核销，不混报或将旧失败文件改为通过。39项不是初始692项完整回归的重跑。

## 运行、截图与人工步骤

唯一7d55 Mock预览：http://127.0.0.1:4177/#/product-data ，strictPort，保留PID104760。
混合ID：http://127.0.0.1:4177/#/product-data?productDataPreview=mixed-ids 。
最终提交后核对工作树HEAD/blob、Vite实际模块和Mock模式，完整运行SHA记录在preview manifest/回执。
无Backend/API/平台写入、新DB/Slot/第二Electron；不触5180/8100及既有Profile/共享stash。

本轮截图/报告在 frontend/test-results/product-data-compact-radio-final/（本地忽略）：

- product-data-compact-compact-product-data-layout-at-1024/product-data-compact-1024.png
- product-data-compact-compact-product-data-layout-at-1440/product-data-compact-1440.png
- product-data-compact-compact-product-data-layout-at-1920/product-data-compact-1920.png
- product-data-compact-keeps-f4ccf--compact-Vue-theme-boundary/product-data-default-detail.png
- 四个product-data-compact-compa-*目录：四主题菜单；product-data-copy-alignmen-*：混合ID/完整提示。
- report.json：本轮19 PASS原始结果、几何附件。仅虚构数据，无Token/Cookie。

ca97接续人工预览建议步骤（不是已执行人工PASS）：

1. 核对精确Candidate/4177模式，初次20条；普通及宽屏看标题预算/全局竖线/必要表格横滚。
2. 切每页10/50，确认回第一页和清勾选；查询/重置仍保留当前条数；字段保存刷新仍保留。
3. 看单行标题悬浮、独立ID行与固定复制；仅虚构字符串验证完整复制，不展示真实凭据。
4. 切主题、打开筛选下拉；打开分组/批量/字段弹窗和商品详情，确认内部仍默认尺寸。

## 未覆盖与停止点

ca97对本精确Candidate的Gate 2、商品数据用户人工确认、真实Integration Electron/系统剪贴板，
以及本轮新Real浏览器未覆盖；不把Owner共享夹具或原05f的Real浏览器证据冒充本轮。
Real商品数据后端仍未接入，真实采集/数据库/日期请求/调度/飞书均未实现或验收。
前端build不是Electron安装包；本次未打包/部署，不合dev/main，无生产发布授权。
正式Gate 1交接材料与本会话回执由规划/ca97协调后续。停止“待用户验收，禁止发布”。
