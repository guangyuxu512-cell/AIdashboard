# 商品采集任务与商品库前端 Mock 契约 V1

状态：`UI_ONLY`。本文件描述显式 Mock 下的页面和交互，不代表手机采集、正式商品库写入、文件导入导出或 AI 能力已接入。

## 路由与复用

- 采集任务继续使用 `/product-selection?tab=collection-tasks`，不新增侧栏、路由或权限码；上层保留 `ContextSwitchBar(appearance="framed")`。
- 商品库继续使用 `/products` 和既有 `product-library` Guard。
- 列表复用 `FilterBar`、`ManagementListSection`、`TableToolbar`、`DataTable`、`PaginationBar`；详情和确认复用 `AppDialog`；图片复用 `ProductImage`，预览主图只在详情内组合 Naive `NImage`。
- 平台代码、名称和图标只取 `entities/platform`；拼多多代码固定为 `pdd`。
- 文件选择沿用已有隐藏原生 input + `AppButton` 组合；未新建 Upload 基础组件或 ZIP 解析层。

## 采集任务 Mock

- 常驻输入仅包含平台、抖店商品 ID／链接或已有店铺口令、输入框和创建按钮。创建时校验格式与活动重复项；校验失败保留草稿。
- 任务公开状态只有排队、处理、完成、失败、取消；回执、处理进度和入库状态只在详情展示。收到回执不等于已经入库。
- 拼多多只提示手机端手动返回边界，淘宝只显示规划状态；不伪造自动关键词采集。
- 候选池 Mock 批量采集和商品库 Mock 重新采集进入同一内存任务源；Real 候选采集没有因此启用。

## 商品库 Mock

- 列表展示标题及业务分组、来源商品 ID／平台、类目、当前价格、采集时间和操作；默认每页 20。
- 业务分组不是平台类目、店铺分组或团队；Mock 支持新建、筛选、批量移动，Real 没有契约时不发送猜测写请求。
- 导入入口支持 TXT、ZIP 和文件夹的文件选择及目标分组；只显示文件清单，不解析、清洗或写入。
- 单商品导出入口对应一个清洗 TXT，批量入口对应 ZIP 清单；Mock 不生成或下载文件。`.txt` 与 `.origin.txt` 均定义为清洗后的兼容文本，不保存原始网络响应。
- 商品 ID 始终为字符串；未知值显示 `—`，真实 0 保持数值；当前价格不从券后价等字段回填；兼容库存值 `999` 不解释为真实库存。

## 商品预览

- 左侧按主图、详情图、SKU 图切换并保持等比；右侧展示基础信息、业务分组、当前价格和采集时间。
- 下方保留 SKU、属性、图片、资料包、采集历史；支持复制标题、基础信息、SKU、全部信息及导出入口。
- AI 改图／审图在右上可见但禁用，明确未接入；本轮没有 Provider、编辑器或审核标准。

## Real 边界与未接入项

- Service Factory 只在构建和运行均为 Mock 时动态加载内存 Store。Real 返回显式 unavailable，绝不加载 fixture、猜测 API 或把操作显示为成功。
- 未接入：手机任务派发与回执、正式任务查询／重试／取消、正式商品库查询与写入、分组持久化、导入解析、TXT／ZIP 生成下载、AI 改图／审图、百应及淘宝采集。
- 本轮无 Backend、数据库、Migration、Worker、Electron 壳或依赖变化。
