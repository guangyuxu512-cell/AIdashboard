# 商品数据已核实字段接回 Gate 1 交接

2026-10-16，Owner 7d55，交接 ca97。沿原 `feat/shop-product-data-frontend-v1`，在已推送的
`1999f877a8eed6cbf98908d38a6d7edaebe6dc81` 上接回 74 指标单页核验，不重建分支或改写历史。
原 a28/1999 候选及证据保留；Green 仍为已包含的 `5a18bd0390cb4b8cbed637d412f7482cefff3f36`。
新完整候选是包含本记录的 Feature HEAD，精确 SHA 与提交后 Real 构建结果见回执和本地忽略清单。
状态为 UI_ONLY；等待独立 Gate 2 与用户验收，禁止发布。

## 已核实的代码与本页覆盖

只读接回 ca97 本机忽略的 `product-list-74-fields-20261016/result.json`；其 SHA-256 为
`7B92BAB188D3C7C87A6923922D50EE47A45127248184CCCCDF1073B27A6D3867`。
ca97 的真实核验在上海 20:42:43，固定 type20/2026-10-14/page1/size10/sale1/content1，HTTP200/st0，
10 行、meta 顶层76/递归83、total146。本树未执行该请求、恢复隧道或连接 Integration。

Owner 离线逐项核对 17 个 code 的当前值：各 10 个非负有限值、单位一致，共 170/170；
显式零与正值分别保留。四新增的准确代码为 product_show_cnt、product_click_cnt、
product_show_click_converse_uv_rate、product_click_pay_converse_uv_rate。
完整 17 项 code/unit/语义表见 `frontend/docs/18-商品数据前端与Mock契约V1.md`。
这是本页字段证据，不是 146 件全量采集、落库、正式 API 或真实界面接入通过。
目标外 7 指标部分仅 unit6 无 value，不能从 meta 存在推断完整或填 0。

## 最小前端改动

`model/metrics.ts` 为 17 项目标登记已核实 platformCode/rawUnitCode，并提供精确代码类型；
这些是字段元数据，不新增请求 DTO、解析器、Real mapper、金额或百分比转换。
两项比率使用 exposureClickRate / clickPayRate 作为前端语义 ID，准确平台代码各自独立登记。
旧 product_click_show_ucnt_ratio / product_click_pay_ucnt_ratio 只存在于列偏好兼容入口及相应测试，
不再用于指标记录、筛选、默认列或平台代码。读取偏好保留位置/可见性并去重，不自动回写原存储。

展示名、19 个中文名称/17 项独立指标、九区间及默认 20 条不变。Mock 仍为独立合成值，
没有复制真实商品数据、把原 unit3 写成元，或把原 unit4 直接当作已确认的百分比显示契约。
现有字段 Tooltip 区分“代码已完成单页核验”与“金额/比例显示换算待确认、真实接口未接入”。
Shared、实体、主题、候选池、照片/ID 夹具、依赖和锁文件均不修改。

## 必须保留的业务未知

unit5 的次数/人数/单由中文 meta 和当前值支持；unit3 金额分/元缩放及 unit4 官方页面百分比显示
未在本轮独立对照，不增加转换或从 Mock 推断。净成交和退款后成交的 meta.tip 均为空，
不宣称全额/部分退款算法已经确认。

同一商品原值成交102、净成交97、退款后成交95、支付时间退款订单7。平台退款后成交95不等同发生退款的7单。
保留用户选定“异常订单”别名和 pay_cnt_exclude_refund 映射，Tooltip 明确不等同发生退款订单数、
不代表风控异常且具体业务定义待规划确认；不得用成交、净成交或退款订单数相减造字段。
总体退款率继续为 pay_refund_ratio，不相加发货前后百分比、不用 sold 子项或退款时间口径替代。

## 定向验证与停止点

- 商品数据 7 文件 69 项单测、lint、typecheck 通过，新增准确17代码/原单位、两项旧比率偏好迁移与未知口径断言。
- compact/main/更多筛选三文件 18 项 Mock 浏览器回归通过，0 fail/skip/flaky。四主题、三视口、
  20 条、字段/分组、九区间、总体退款率 Tooltip/详情、默认边界及跨页恢复均在范围内。
- 最终报告在忽略的 `frontend/test-results/product-data-verified-metrics-v1-unit/` 与
  `frontend/test-results/product-data-verified-metrics-v1-browser/`；原 65/17、67/18 及失败报告保留，不累计为本次重跑。
- 精确候选提交后执行 Real production build 并核 Mock/夹具标记；以同 SHA 回执及本地清单确认构建结果。

只沿原 4177 strictPort Mock 进程预览，不启动/重启服务、不操作 ca97 的窗口/Profile/端口或 81a1 的资源/stash。
本轮平台/Signer请求、DB连接/写入、Backend/Worker/Electron/Schema/Migration/调度/生产变化均为无。
Feature DB、Migration Slot：无。Real 数据源仍 available=false，无猜测请求或 Mock 回退。
新候选 Real 浏览器、Integration Electron 与用户人工确认未覆盖；ca97 按精确新 SHA 独立 Gate 2，不合 dev/main 或发布。
