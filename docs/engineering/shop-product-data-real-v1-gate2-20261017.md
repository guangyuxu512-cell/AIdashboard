# 商品数据真实接入集成审查

Candidate `5915009d85be2ea912d8498dc0807b141938f399`，运行实现 `c448deaabe5a68b4a50146f4928022fb26bf1385`，精确Green基线 `bef7093b755cea60fda55bbcc6177b5723d4738a`。ca97已完成独立源码和离线技术复核；Integration数据库、正式API及新的真实平台全页闭环尚未验证，不能据此标记总Gate2通过、Green或发布。

## 独立复核结果

精确Git归档位于ca97本地忽略 `.codex/review-product-data-5915009-utf8/source`，没有Owner保护配置。复核未修改Feature源码、Owner工作树或已有服务，没有连接数据库、启动窗口、请求平台或Signer。

| 检查 | 结果 |
| --- | --- |
| 固定路径解析、有限全页、Connector、DTO及Schema单测 | 87通过，0失败、错误或跳过 |
| 共享HTTP、原选品解析/Connector及经营Collector回归 | 78通过，0失败、错误或跳过 |
| 商品数据前端测试 | 83通过，0失败或待执行 |
| 前端类型、lint | 均通过 |
| 精确Real production构建 | 通过，20.94秒；既有大chunk警告保留，不为此调整依赖或架构 |

构建商品chunk `ProductDataPage-phYa2Fwm.js` SHA256为 `A7B644CACC4D6F814881F9333575EDBA31308336865F2283BDB56852B28FC2B0`，与Owner交接一致。测试为离线或合成响应，不是平台数据证据。

已审四表身份和复合外键、非空Actor幂等键、原窗口回放、跨进程容量及租约、全页去重与完整代原子发布、失败旧代保护、当前人员/Team/Shop授权、SQL筛选排序分页、Session版本CAS、只读刷新与typed Real适配。47迁移仅新增本域结构，降级精确限制专用Feature库且拒绝任一新业务行；未改已应用47。原Shared紧凑样式继承af6，两项差异如实保留，不称相对Green无Shared修改。

Owner报告的45项真实Feature PG及947项后端、856项前端全量结果仍属于Gate1证据；ca97没有将其改称自己运行的Integration结果。当前源审及上述离线检查未发现必须退回的业务缺陷，但不是未覆盖项的通过结论。

## 剩余边界与下一步

唯一active Slot `20261017_0047` 与专库 `control_center_feat_shop_product_data`、8102/4177仍属7d55。经营恢复复用81a1旧Feature库/0046和8101/4176，不占这些资源。Integration迁移/运行按既有流程单独准备，不将Feature连接复制过去；生产仍为fe7及0046。

ca97已作一次有界只读Integration预检，连前/连后精确核目标 `control_center_integration` 和最小应用角色：实际单一0046，四张商品表均不存在。HuanYu Integration UUID为 `c448f225-b141-409b-bc94-12f1ae74ee04`、平台身份243321624、启用，已有正常Session为valid v9，最近采集/验证为上海10月17日06:53。只读检查没有解密、平台验证或写入；并不证明当前freshness已满足。库内2020条旧经营活动夹具保留，不让新测试全局领取或清表。迁移前精确备份已交Main按既有管理通道准备，未执行47；同一Integration Runtime短时串行验收，不阻碍双方Feature开发或技术审查。

新的真实平台请求目前未获对应预算。下一步先由规划核明确的Integration店铺、原有合法Session、原生固定窗口、一次有限全页及必要权威验证预算，再执行正式提交、完整入库、查询和Real展示。总数超预算、认证/风险或业务失败须停止，不无限重试、自动换日、复制生产Cookie或要求用户重复机械登录。

真实空商品包装、金额unit3/比例unit4官方显示尺度仍未核定，继续保留未知和原值，不能填0或猜单位。分组、自定义日期、其他售卖/载体、自动每日和删除不开放。没有本Feature生产发布授权，也没有新Electron安装包要求；原身份与窗口路径未改，不重做已确认的登录/关闭测试。
