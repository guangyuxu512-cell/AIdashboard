# 商品数据单位换算证据 V1

2026-10-17，Owner 7d55，供ca97复核。结论限定于本功能固定17指标的罗盘商品列表当前值路径：unit3金额原值除以100得到元；unit4原值为比例分数，展示乘以100并带百分号；unit5计数不缩放。原值和原unit完整保留，不由订单、人数或金额重新计算任何比例。

## 官方商品列表调用链

入口为[官方商品列表](https://compass.jinritemai.com/shop/commodity/product-list)。无认证读取的HTML将`/shop/commodity`交给版本1.0.0.3672的[商品微应用入口](https://lf6-cdn2-tos.bytegoofy.com/gftar/cmp/ecom/compass_shop_merchandise/1.0.0.3672/html/main/index.html)，不是仅据父页面的通用枚举推断。

微应用[main资源](https://lf3-fe.ecombdstatic.com/obj/ecom-cdn-default/cmp/ecom/compass/merchandise/static/js/main.720ba9db.js)在字符偏移3585登记精确商品列表路由，加载chunk363、入口模块11650；入口HTML的runtime给出chunk363的实际名称与版本。[商品列表资源](https://lf3-fe.ecombdstatic.com/obj/ecom-cdn-default/cmp/ecom/compass/merchandise/static/js/async/shop_product_list.7c16de40.js)内的链路如下。

1. 模块11650使用37603的表格适配器；适配器约3038处按响应meta生成指标列，约3795处指向`cell_info[index_name]`。33017的L适配器约6500处只解包当前index_values，没有数值缩放。
2. 约4021至4829处读取`cell_info[code][code+'_index_values'].index_values.value`并传给EUE。导入绑定指向模块54761。该处只覆盖比例显示小数位，17指标均为2位；例外complaint_ratio不在本次17项中，没有price或ratio的numeral倍率覆盖。
3. 商品表只为product_info定制内容、为pay_amt定制宽度；其余指标列沿meta默认渲染，列编排保留这些列。没有为本次3金额或4比例重算业务分子分母。

微应用[669资源](https://lf3-fe.ecombdstatic.com/obj/ecom-cdn-default/cmp/ecom/compass/merchandise/static/js/669.735404f5.js)中，模块54761约117523处导出EUE到tn；tn约223644处读取value/config，默认indexValue分支约230783处调用nF。nF约163781处按value.unit分派：枚举约160863处确认PRICE3、RATIO4、NUMBER5，约164370处金额默认乘0.01、前缀人民币符号，比例乘100、后缀百分号。约161552处numeral操作为乘法。商品表传入的config不覆盖这两个倍率。

父页面[4977资源](https://lf3-fe.ecombdstatic.com/obj/ecom-cdn-default/cmp/ecom/compass/static/js/4977.e4a72b73.js)的模块38813/tj有相同倍率，仅作为交叉核对；实现依据是上述真实商品路由到微应用formatter的链路。偏移按UTF-8解码后的字符索引记录，不当作字节偏移或源文件行号。

| 资源 | 本次下载的SHA-256 |
| --- | --- |
| 父页面HTML | BBE39D3E00147A7915B4843217B0B74902E05ED5D2A29B311ACA6A50E58AFCB1 |
| 商品微应用HTML | FD4E14ED82E01E4BF245246802020B788E8814718F2FD20DDE8ED307A8BACE5B |
| 微应用main.720ba9db.js | E7D51BB78F6A5264DC8F12504CF92F4248FA6C89AF331843F21BA2471BCB246D |
| shop_product_list.7c16de40.js | D356F5AAEB27F7708508CE0F1D8C45026C15A18D6C06186FAD08D9ADCD74AEEB |
| 微应用669.735404f5.js | 36361DE3CACAD2BEF366C014AE5351B0E4A4129BE5BF0099CD6E664302642A38 |
| 父页面4977.e4a72b73.js | 3EE5706C7B7BF526C36D82FF333D589F74405AC249859E8A8AC43D2BB44A4297 |

下载和辅助资源保留在Owner ignored `.codex/product-data-real-v1/official-units-20261017/`，只读取静态公开资源，不执行其代码、不携带认证、不请求业务取数接口。

## 既有真实响应关联与独立公式核对

ca97原受控`platform-observations.jsonl`中，取各period最后一条page1的parsed-product-page白名单观测；本功能strict parser直接从上述相同当前值路径取得原Decimal、unit和state，不从meta存在或其它指标计算值。三个窗口样本的3金额均为available/unit3，4比例均为available/unit4。只复用已存在的1d178、7d229、30d344成功代，未重采；完整原始响应、Cookie或签名不进入测试或本文。

| 窗口 | 支付金额 raw→元 | 客单价 raw→元 | 支付时间退款金额 raw→元 |
| --- | --- | --- | --- |
| 1d | 88820→888.20 | 1096→10.96 | 4180→41.80 |
| 7d | 404513→4045.13 | 1021→10.21 | 30013→300.13 |
| 30d | 1477108→14771.08 | 1014→10.14 | 143938→1439.38 |

| 窗口 | 点击率 | 加购率 | 点击成交率 | 总体支付时间退款率 |
| --- | --- | --- | --- | --- |
| 1d | 1.66% | 0.06% | 6.73% | 4.71% |
| 7d | 1.51% | 0.05% | 7.21% | 7.42% |
| 30d | 2.02% | 0.07% | 6.51% | 9.74% |

21个完整原数值及逐项固定期望分别保存在Backend解析回归和Frontend单位回归中，使用合成身份和文本，不放进Mock商品数据。金额归一化保留所有Decimal位，比例规范值仍为原分数，只有最终展示按正数十进制half-up取2位；不复刻JavaScript浮点误差或提前舍入。某行某项missing/null/invalid、unit6或单位不符继续显示未知；真实0显示0.00而不是未知。

名称解释与单位证据分开：原白名单及Root本次meta核对确认net_pay_cnt为“净成交订单数”、pay_cnt_exclude_refund为“退款后成交订单数(支付时间)”，两项index_tip均空。已证实的是代码、官方名称及原值/unit，不是全额/部分退款算法、风控异常定义或样本差额关系。保留人类已确认的“真实订单／异常订单”别名与原映射，现有Tooltip展示官方名称和限制；不换成退款订单数，也不重新定义指标。

## 查询与历史兼容

四项比例区间的API min_value/max_value使用原分数十进制字符串，含下限、不含上限；UI填1表示1%，发送0.01。复用既有Number输入控件的规范十进制文本，再做精确小数点位移，不把Number除100后的浮点尾数发给服务器。数量超出安全整数范围仍拒绝。SQL在全量授权事实中同时校验available与对应原unit后组合筛选、排序、计total再分页；不在前端当前页补筛，也不使用显示舍入值比较。

保持17指标code、别名、request_contract、metric_contract、所有source/rolling hash及已应用0047逐字不变，继续查询原三代751条快照，不隐藏或重写它们。GET的unit_verified表示当前已核定的显示尺度，不等于每项数据都有值；原采集回执unit_complete_rows=0保留其当时的覆盖语义，不回填。392预算反馈修复和原失败均保留。

本次只补已确认路径的单位、展示与四项比例区间及金额/比例排序，不开放分组、自定义采集窗口、其它平台或其它sale/content。新候选的Integration Renderer、原生Electron及生产验收仍由ca97/Main按各自Gate核销；旧三窗口原值校对不替代新候选验收。
