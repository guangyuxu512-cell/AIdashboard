# 候选池共享商品信息 Gate 1（2026-10-15）

Owner81a1，分支feat/product-selection-candidate-result-filters-v1，接续精确
f876f83ec558766617ed2b07ccf87f213d2493cf；Candidate完整SHA见最终正式Handoff。
已回读规划人类turn01a13d61-89e0-76b0-b852-166bdf24e863：商品数据暂缓，只统一候选池商品信息。
ca97确认最小依赖及唯一归属；不是商品数据整体接入或生产授权。旧成果/0046/本机材料保留。

## 已有 → 复用 → 必要调整

| 已有来源 | 本次用途 | 必要调整 |
| --- | --- | --- |
| b364a89a9955ffe4aae1c3fb6dbfcabfd0dedf8f / entities/product/ui/ProductInfoCell.vue | 合并候选缩略图/标题为商品信息，主图、单行标题、ID及固定复制槽 | 缺ID显示—并禁复制；安装Naive2.45的NEllipsis已实测点击异常，新组件仅复用NTooltip/省略标签兼容 |
| 同源ProductImage.vue及index.ts | 唯一图片实体/公共出口 | no-referrer、lazy、contain、NImage预览/重试不变；来源可追溯，不引入其它模块 |
| 原ExternalProductImage | 保留详情原Props/导入 | 只薄转发到ProductImage，不保留第二图片实现；Entity测试不反向导入Feature |
| 原AppButton/Copy/useMessage | 固定槽、复制与成功/失败反馈 | 原字符串，不转Number、不含展示前缀；防重复，失败仍可手动选择文本 |
| 原DataTable/columns/useElementSize | 实际容器宽度和固定列 | 合并后11列，仅调整原图片/标题/商家/类目预算；原六数值/状态列和操作不变 |

商品信息最小260px，选择44、商家至少66、类目至少52、操作220。大屏原分配保持，
窄屏保留必要横滚和左身份/右操作固定，不隐藏/删字段。64px图及8px上下/12px左右padding，
常规行约81px；标题单行，ID行固定grid槽最大194px（160+4+30），不按ID长度定位按钮。
标题/ID被省略仍可悬浮全文，复制完整字符串；缺ID不生成替代商品ID。

## 范围与保留

未合入商品数据分支、页面、路由、Mock、服务或后端提案；Mock数据和夹具未清理。
策略列表/抽屉、长标签提示、所有其它字段/操作/查询、权限及Real无Mock回退保持。
没有Backend/Electron/DB/Migration/依赖/全局字体或主题修改；0046 SHA256仍为
F87B00229065BADC506CE3BE38E59AB9E7B2DF1833918941D8F4833F924C2F9C。
只用原4176前端资源，不启动第二Electron、不占5180/8100、不清Profile、不取平台或写共享库。

## 实际检查

frontend lint/typecheck PASS；Real production build PASS/20.84s，仅原>500kB分包告警。
`exec vitest run src/entities/product src/features/product-selection src/shared/ui/AppSelect.spec.ts src/entities/shop/ui/ShopSelector.spec.ts`
19文件140项PASS，含复制原字符串/缺ID/重复点击/失败反馈、图Facade/预览配置/重试和既有选品回归。
格式检查、最终lint、git diff --check均PASS，Real产物扫描无选品Mock handler/商品照片夹具引用。

浏览器Mock：`exec playwright test --config ../.codex/selection-product-info-mock.config.ts`，
14个不同场景完成（最终整组13/14，剩余旧布局断言修正后单独复验1/1 PASS/40.2s；不叠加重跑计数）。
覆盖四主题1366×768、1440×900、1920×1080、2560×1390，短/18位/36位字符串及缺ID、
标题/ID实际点击零pageerror、固定复制槽坐标、全文悬浮/选中文本、64px图/约81px行、
原列排序分页/选中/批量部分失败/屏蔽/图片预览与两源无CORS/失败重试、策略和跨模块导航回归。
另保留2240附加宽屏、详情边框/字号/两个时间字段/缺值零值的既有受影响检查。
复制API在隔离浏览器中拦截验证参数，未称系统剪贴板或原生Electron已验。

Real Renderer/全部API拦截：`exec playwright test --config ../.codex/select-label-tooltip-playwright.config.ts`
四主题4/4 PASS/约1分钟，1440/1366、长店铺/策略/批次、URL/刷新/前后退、屏蔽/basic进度及
Real无Mock导入继续通过。没有实际平台请求、DB或原生验收，不把合成API响应当真实更新成功。

图片：忽略目录 `.codex/selection-product-info-mock-final/` 的四主题整页，
`.codex/selection-product-info-layout-complete/` 的两视口列表/详情及行宽/间距/颜色JSON，
`.codex/selection-product-info-real-verified/` 的Real/API拦截列表/详情与长标签。
Owner浏览器运行127.0.0.1:4176，源码与最终Candidate功能字节对应，不是5180/Electron截图。

初次typecheck因tooltipStyle推断为宽泛string失败，已显式CSSProperties；单测初次消息查找在
组件树而实际Naive消息Teleport到body，已改真实位置；没有改消息实现或延迟。
首轮布局测量残留横滚位置，改为每次截图前恢复左端；新候选最初300px身份下限使普通视口
状态列需横滚，现仅三个文本列内预留260px并按原预算分配，1440完整展示，1366保留必要横滚。
旧E2E仍引用12列/旧nth索引、两行标题、88px独立图片及旧每小时文案，逐项同步现行结构；
列宽之和使用实测分数像素与行宽比较，不先逐列取整后相加（会累计约2px误差）。
失败材料保留，不伪装首次全通过。

## 交还ca97

提交/推送新Candidate后更新精确5180 Renderer、保留同一Electron/人员会话/Profile。
只补新商品信息列普通/最大化及必要窄窗口人工确认；旧策略/长名称已通过不重复。
新布局待人工确认；真实单项basic正式执行仍由ca97原Gate2按授权边界完成，本UI不替代平台证据。
不交Main或发布，未增加后台能力、真实采集、手机、百应、商品数据业务或残留清理。
