# 商品数据紧凑复用与默认20条 — 接入草稿／依赖缺口

2026-10-15，Owner 7d55，原分支 feat/shop-product-data-frontend-v1。
本轮状态：Gate 1 NOT_READY；不是验收候选、Green或发布批准。草稿完整SHA见回执及本地manifest。
原 b364a89a9955ffe4aae1c3fb6dbfcabfd0dedf8f、全部历史及虚构夹具保留。

## 授权、依赖与合并

已直接回读规划人类turn01a13e9c-74c8-7950-873a-8c6e7aa0b9f8：批准商品数据接入已确认样式，
并要求默认每页20条，不是20页；选品与商品库由各自Owner处理，本树不实现它们。
ca97已交付纯共享精确 1a8078d0cd9917afc11454e84ff0d13d15a1a2f2，
分支 feat/compact-product-list-foundation-v1。38e9abf的人类可见候选池确认只作为依赖消费门禁，
不扩写普通/最大化或剪贴板专项通过，也不等于商品数据验收。

- 先正常提交本页默认20条：b41dbb6744b3c28f774f595f94ca53b252b9aa19，12项相关单测通过。
- 再正常 no-ff 合并精确共享SHA，合并提交 6b707c7648e8c9e43494feaa0eba14ab0e4c0df4；
  两父为b41dbb6及1a8078d，没有合入整条选品Feature或0046业务。
- ProductImage、ProductInfoCell、ProductInfoCell.spec三处add/add采用受审共享原文件。
  ExternalProductImage包装冲突只有注释差异，运行代码相同，采用受审共享注释；无其它冲突。
- 合并及页面接入后，共享/商品实体/ShopSelector/选品目录与1a8078d无运行差异；
  Backend代码、Migration、Worker、Electron及依赖定义相对b364无变化。

## 已有 → 复用 → 必要扩展

| 已有 | 复用 | 本页必要变更 |
| --- | --- | --- |
| 商品数据列表、查询草稿、全量排序后分页、分组与个人列偏好 | 保留原ViewModel/Mock/service和现有动作 | 初次进入20条，仍可选10/20/50/100；切换回第一页并清选择，查询/重置/排序保留当前选择 |
| ProductInfoCell/ProductImage | 精确共享的单行标题/完整提示、字符串ID/缺失保护/固定槽、48px显式图片 | 仅列表传density=compact；详情默认64px不变 |
| ManagementListSection/FilterBar/TableToolbar/PaginationBar | 显式compact、局部Naive主题及全局主题细竖线 | 列表/筛选/工具栏/分页启用，已有弹窗/详情声明为边界外兄弟VNode |
| 本页字段定义与宽度、既有VueUse useElementSize模式 | 本页既有数据列/顺序/居中与固定列 | 商品信息预算304px；读实际容器，将宽屏剩余空间按现有字段宽度分配，避免浏览器撑长标题 |

不是整页缩放；不改:root默认尺寸、主题颜色/字体家族/导航/圆角，不新增基础控件或第二套compact。
当前只持久化个人列ID/顺序；每页条数原本仅组件内存状态，没有需覆盖的已存分页偏好。
不新增分页存储、不清localStorage/Profile；用户当前页容量可切换，新挂载页面才取初始20。
商品库保持占位，未来默认20仅记录；不新增字段、筛选逻辑、日期/实时、API、平台、调度或飞书。

## 实际验证与未过项

- Vitest定向9文件/38项PASS：商品数据、商品实体、共享density、分页、表格。含默认20/切换/
  页码与选择重置/不写存储、弹窗边界、304宽度/字段顺序、原分组失败草稿及Real不可用。
- lint PASS；vue-tsc typecheck PASS；Real production build PASS，既有大chunk提示保留。
- Mock完整浏览器一轮 product-data-compact-v3：19项中14 PASS、5 FAIL。
  四项为同一个Radio尺寸缺口；另一项测跨页时没有等旧路由卸载，误读旧列表输入。
  后者补等待旧组件卸载后，在 product-data-compact-overlay-final 独立重跑1项PASS。
  因此仍有4个Radio断言未通过，不能把本轮写成全部通过；未删断言、skip或放松尺寸。
- 已通过的真实浏览器范围：默认20/10/50切换与页码/勾选/重置，三视口单行标题与2/18/98位
  复制回读完整一致、固定28px槽；既有分组创建/更名/批量/删除影响、字段配置保存刷新、排序、
  失败恢复、宽表滚动；四主题及teleport下拉12px/28px；分组/批量/字段弹窗14px/34px、
  详情标题14px/ID13px/图64px/复制30px，以及切换店铺页恢复默认14px/34px。
- 三视口1024×768/1440×900/1920×1080：商品列实际304px，图48px，行自然65px，
  ID12px/文字槽160px/复制28px；卡片padding12px、组合gap8px。长标题不增加行高，不裁行。
- 初轮宽屏浏览器自动分配会把配置304扩到372.14px，仅设列maxWidth未生效；已按本页实际
  容器分配其余数据列解决，后续三视口标题检查通过，不改共享表格或照搬候选池预算。
- 中途单测存在新测试漏import及店铺watch清选择时序问题，已只修测试并最终38项通过；
  菜单/弹窗几何检查等待过渡完成，尺寸断言保持。跨页错误等待已如上单独核销。

### 唯一当前共享缺口：日期快捷Radio

1a8078d的createListDensityTheme包含Button/Input/Select等映射，未包含Radio。
页面原AppRadio仍由NRadioGroup/NRadioButton渲染。三视口及独立可选筛选探针均实测
14px/34px，而任务规格是12px/28px。不是动画取样或其它页面默认尺寸。
原有更多筛选的NumberInput与自定义日期输入触发器已经12px/28px；本次仅测试现有显示，
未新增日期或筛选能力。需唯一共享Owner81a1补充最小Radio尺寸映射、保持默认/颜色不变，
ca97交新的精确纯共享依赖后正常no-ff消费再复跑。7d55不越界修改共享层或写页面deep覆盖。

## 证据、资源与接续

保留同一7d55 Vite PID104760、127.0.0.1:4177 strictPort Mock，无新服务/端口/Electron/DB/Slot。
截图/报告均本地忽略，不含凭据；人工预览为草稿，不据此补写人工PASS。

- frontend/test-results/product-data-compact-v3/report.json：完整一轮原始14/5结果及几何附件。
- 同目录 product-data-compact-compact-product-data-layout-at-{1024,1440,1920}/test-failed-1.png：
  当前页面，真实保留Radio尚未达标的差异。
- 同目录四个 product-data-compact-compa-* 目录：四主题菜单截图。
- 同目录 product-data-copy-alignmen-*：混合ID、完整悬浮提示和纯字符串复制截图。
- frontend/test-results/product-data-compact-overlay-final/：独立通过的详情/跨页恢复证据。
- frontend/test-results/product-data-compact-optional-filter-probe/：Radio14/34、Number/Date12/28。

新候选Gate 1、ca97 Gate 2、商品数据用户人工确认均尚未完成；真实Integration Electron及
本轮新Real浏览器未覆盖，不复用旧05f的Real浏览器记录冒充本轮；Real后端仍未接入。
尚不推送为验收候选，不合dev/main、不部署/发布。待共享Radio修订后完成剩余验证和正式Handoff。
