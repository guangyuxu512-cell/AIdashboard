# 商品数据字段白名单与稳定排版 V1 Gate 1 Handoff

2026-10-17，Owner 7d55，在既有 `feat/shop-product-data-real-v1` 上从已获Gate 2A的候选 `3913d4bb20a5a9784d800dce1ef3cec7124ef615` 追加纯前端修订。Gate 1通过；精确完整候选以最终Git回执为准。ca97仍需执行增量Gate 2和真实Integration Electron确认，未合入dev/main、未释放0047、未发布。

## 实现范围

新增模块级展示白名单 `frontend/src/features/product-data/model/display-fields.ts`。列表、字段配置和详情只消费这份白名单，指标名称、单位、格式、平台代码和值继续由原 `metrics.ts` 和17项Real映射提供。

| 分组 | 固定展示顺序 |
| --- | --- |
| 基础字段 | 店铺；商品信息／ID固定左列，操作固定右列 |
| 核心指标 | 曝光、点击量、点击率、加购量、加购率、真实订单、异常订单、转化率、退款率 |
| 交易指标 | 支付金额、订单数、成交人数、客单价、退款金额、退款单数 |
| 流量指标 | 曝光人数、点击人数、曝光点击率、点击成交率 |

曝光点击率复用 `exposureClickRate`，点击成交率复用 `clickPayRate`；两项仅增加展示显隐键，表格值、详情值、Mock排序和Real排序均指向原指标。没有新增平台字段、API参数、持久化业务列或计算公式。退款率仍是支付时间总体退款率，包含发货前后；未采用参考图中的发货后退货率。可售库存无准确来源，本轮不显示、不补0。

新用户默认店铺加核心组。原个人偏好键不变；旧显式选择中仍在白名单内的字段保留，旧比率和退款率替代ID沿既有规则迁移，废弃显示键过滤，结果按固定业务顺序排列且读取不回写存储。结算金额、退款时间旧口径、旧未核实退款单数、库存及其它白名单外字段保留在兼容模型和数据读取中，没有删除或重绑。

列表移除按容器比例扩张列宽：选择44px、商品信息304px、操作88px固定，店铺140px，指标沿既有130px／150px宽度并同时声明最小和最大宽度；中间列按白名单顺序，空间不足只出现表格横滚。字段配置使用既有AppDialog、AppCheckbox和AppButton按四组排列，不保留上移／下移。详情使用既有DetailDrawer、ProductInfoCell和NDescriptions按同一四组对齐；抽屉正文滚动，普通及窄窗无页面横向溢出。共享组件、全局主题、compact密度和默认20条未改。

## 修改文件

- 新增展示元数据与定向测试：`model/display-fields.ts`、`model/display-fields.spec.ts`。
- 偏好固定顺序和白名单过滤：`model/column-preferences.ts` 及其测试；`model/types.ts` 只增加展示类型，不改行数据或API DTO。
- 列表、字段配置、详情：`ProductDataTable.vue`、`ProductFieldConfigDialog.vue`、`ProductDataDetailDrawer.vue` 及对应测试；`ProductDataView.vue` 仅适配新的展示类型和隐藏排序清理。
- 别名排序复用：Mock和Real前端适配器只把展示别名还原到既有指标，原请求路径、范围和字段不变。
- 浏览器专项更新为新白名单、固定顺序和详情分组预期；前端契约18同步当前边界。

无Backend、Migration、0047、数据库、Electron、Worker、Mobile、依赖或共享基础Owner文件变化。

## 验证结果

| 验证 | 实际结果 |
| --- | --- |
| 商品数据定向Vitest | 9文件55项通过，0失败 |
| Frontend全量Vitest | 169文件918项通过，0失败；既有AI工作台jsdom XHR警告保留 |
| 商品数据Mock浏览器专项 | 24场景通过，覆盖1024／1440／1920、四主题、字段分组、固定列、内部横滚、详情、偏好刷新及原筛选／分页／复制／分组回归 |
| vue-tsc | 通过 |
| Frontend全量eslint | 通过 |
| Real production build | 5805模块，21.14秒，86个JS资产；商品页 `ProductDataPage-7HnN9EKJ.js` SHA-256 `3136CE540153350670208C2051EEF77CF905D7572F62B2F74CAE35F8D7C648B6`；保留既有大chunk警告 |
| 默认Verify quick-offline | 19.84秒，exit0；28项精确已知未修复、0新增失败、0 stale；报告SHA-256 `5585C7FE038DA1203DC349043A70FDEA75128B536C13D261EF5DB96F97740EE3` |

浏览器实际截图确认：1024宽字段弹窗保持在Viewport内，四组两列对齐且只滚动正文；详情抽屉四组单列对齐，标签和值没有横向溢出。截图、构建和Verify报告均为本地忽略材料，不含Token、Cookie或真实商品数据。

## 保留成果与未覆盖项

原1d／7d／30d的178／229／344件冻结结果、12767项原值单位证据、17项映射、九项筛选、旧成功／失败回执、d3单测与Feature PG证据全部保留。本轮没有连接数据库、执行DDL、重采平台数据、发送Signer请求、启动Backend或Electron、操作Profile／Session，也未改别名业务含义。

本轮未覆盖真实Integration API和Electron原生窗口下的新字段布局、用户对本次候选的人工界面确认、安装包、生产数据或Release Gate。默认Verify没有运行 `--full`／`--strict`、PostgreSQL、容器、真实平台或原生Electron；这些不能写成通过。

## Gate 2检查点

ca97应核对精确候选和本文件列出的增量，复用既有业务与PG证据而不重复采集。集中原生确认至少包括：默认店铺加核心组；配置仅四组白名单且固定顺序；结算金额、旧退款口径和库存不出现；交易／流量选择刷新后保留；两组别名与核心值一致；商品信息和操作固定，中间只在表格内部横滚；详情四组对齐且窄窗无溢出。

Gate 2及用户确认前保持：待集中原生确认，禁止合dev/main或发布。
