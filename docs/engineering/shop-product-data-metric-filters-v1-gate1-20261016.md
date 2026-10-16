# 商品数据指标命名与区间筛选 Gate 1 交接

本记录封存原指标筛选候选 `a28f8d3ac10c6c79ce05598db5f02071b877317b` 的阶段证据。
同日用户已改用总体“退款率（支付时间）”，替代下述旧发货后目标；最新修正交接见
`shop-product-data-refund-rate-v1-gate1-20261016.md`，不可用 a28 作为最新口径候选。

2026-10-16，Owner 7d55，交接 ca97。本增量沿 `feat/shop-product-data-frontend-v1`
在已推送候选 `b9fa5717c3a656ae1f3f4a5376df1e556c9b69df` 上接续；原完整候选为上述 a28f8d3，
该阶段的精确 SHA 及提交后 Real 构建结果见原回执与本地忽略的验收清单，不作为新退款率修正证据。
基线 Green `5a18bd0390cb4b8cbed637d412f7482cefff3f36` 已在原候选祖先中，远端 dev 复核一致。
未重建分支、rebase、reset 或合入未审业务。状态仍为 UI_ONLY，待独立 Gate 2 与用户验收，禁止发布。

## 授权与修改范围

已回读规划聊天人类 turn `01a1446a-0a38-75a1-b3b4-4a348c4d8651` 的“分配任务”，
及 `01a14457-9a36-7cd3-a8e0-60b8aef1911f` 的名称对照。只改商品数据 Feature、相应前端测试与契约；
不改 Shared、商品/店铺 Entity、候选池业务、主题、依赖或锁文件。图片、混合长度 ID 夹具与原报告保留。
Backend、Worker、Electron、数据库、Migration、调度和通知均无修改或执行。Migration Slot、Feature DB：无。

`model/metrics.ts` 统一 17 项目标指标、19 个中文名称及两组比率别名。表头、字段配置、详情与筛选标签
复用同一注册，口径 Tooltip 标注官方目标名；异常订单明确退款相关而非风控。
保留原字段偏好键、有序 ID、可见性及保存失败草稿；读偏好只在内存规范同义别名，不自动回写。
旧 receive_amt 更正为结算金额，旧退款时间金额、未核实退款单数和库存四项兼容列保留，
不重绑支付时间退款；后两项显式未知。两组比率别名不生成重复列或指标副本。

更多筛选补齐九项预设及自定义上下限，默认不限。售卖类型为全部/自营/合作，载体为全部/直播/短视频/商品卡/图文，
并保留店铺、ID、名称与店内分组。复用 AppSelect、AppNumberInput、FilterField、vee-validate 与 Zod，
不新建全局筛选框架或基础控件。自定义上下限纵向排列，避免 160px 控件内步进按钮挤压数字。
居中、竖线、12px/28px 紧凑列表、单行标题、ID 前缀/复制固定槽、默认 20 条及详情默认尺寸继续保留。

## 查询与数值规则

完整区间表及 17 项语义见 `frontend/docs/18-商品数据前端与Mock契约V1.md`。
全部区间采用 `[min,max)`，末档 `>= min`；自定义支持合法单边界，负数、非有限数、数量小数、
上下限倒置或相等均校验。两边留空等同不限；存在有效边界时缺失、空、无效及错误单位不进入范围，合法 0 不被排除。
转化率按连续 0–1%、1–2%、2–4%、4–6%、6%以上处理，覆盖截图遗漏的 4–5%，不复制缺口。

页面百分比 1 明确编译为 Mock fraction 0.01，数量不缩放；`ProductMetricInterval` 是显式语义/边界/单位草案，
不是平台 Query 或正式 API DTO，不据此推断原始 unit 3/4/5 或金额倍数。
Mock 先在完整集合上组合筛选，再全量排序、计算 total 和分页，不只筛当前 20 条，也不触发采集。
查询应用深复制后的草稿，回第 1 页并清勾选；非法草稿保持原结果和页码，隐藏列不清筛选。

## 定向验证

- `pnpm exec vitest run src/features/product-data --maxWorkers=2`：7 文件 65 项通过。
  包含九项临界值/唯一归属、连续转化率、百分比、缺失/零、上下限校验、完整集合组合查询、分页、
  深复制草稿、隐藏列后保留筛选、旧偏好/别名去重、失败恢复及 Real 不可用边界。
- `pnpm run lint`、`pnpm run typecheck`：通过。
- 既有配置下运行 product-data-filters、product-data-compact 与 product-data 三文件：
  17 项浏览器通过，0 skip/fail/flaky；四主题、三视口、菜单/Radio、20 条分页、字段配置、分组及
  错误恢复、默认详情和跨页隔离均在范围内。最终目录为
  `frontend/test-results/product-data-metrics-v1-final-layout/`，含 report.json、截图及尺寸附件，全部忽略。
- Owner 实看 1024/1440 截图；修正自定义数字挤压后，1024 截图中 1000 与上下限含义可读，查询及分页仍在视口内。
  精确提交的 Real production build 在提交后执行并核 JS 内 Mock/夹具标记，结果须与交付 SHA 一致。

首轮新增浏览器用例为 1 通过/3 失败，原报告在 `product-data-metrics-v1-first/`：
两个角色定位误用了 spinbutton（既有 Naive 控件实际为 textbox），另一个因菜单退出动画未结束产生双匹配。
仅修正测试定位并显式等待菜单关闭，后续 4 项通过；截图复核另发现并修正实际数字挤压，最终完整 17 项通过。
原 b9/03bd 的单位、复制及旧失败报告保留，不把它们累计为本次重跑，也不以浏览器替代原生验收。

## 尚未核实的真实映射

本增量没有真实 mapper，原 code 形状的前端 ID 仍只为偏好兼容。Real 数据源保持
`available=false` 与“商品数据接口尚未接入”，不发猜测请求或回退 Mock。
ca97 正在独立核验 74 指标，不因通道等待追加平台请求。其旧样本已支持 net_pay_cnt 和 pay_cnt_exclude_refund 的名称/数值，
但没有全额/部分退款算法证据；不以成交单减净成交单计算异常订单。
sold_pay_refund_ratio 的实际名为发货后退款率（支付时间），不能冒充已核实的发货后退货率。
新增次数/点击比率实际返回、单位和金额缩放仍待正式核验；旧响应的 unit6 无 value、-1、缺字段不补 0。
自定义日期不扩官方支持声明，不新增自动日期回退或采集入口。

## 预览与停止点

本树独立 Mock：`http://127.0.0.1:4177/#/product-data`，strictPort；进程归属与候选标识保存在
本树 `.codex/product-data-metrics-v1/`，不提交 PID、构建产物或截图。旧预览已退出后才恢复该既有端口，
没有停止其它实例或占用 ca97 的 5180/8100、81a1 的 4176/8101。Integration 当前 b9 归档、唯一 Electron 与 Profile 均未操作。

ca97 应加载本次完整候选并独立 Gate 2，不能用 b9 原生确认或旧真实字段样本代替新页面验收。
本次未执行新候选 Real 浏览器、Integration Electron、系统剪贴板或用户人工验收，不合 dev/main，不构建安装包或发布。
回退保留当前分支、旧 b9、偏好和全部材料；共享历史按流程 revert，不 reset 或清 Profile。
