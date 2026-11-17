# Worker 预检纯算签名 Gate 1

- 基线：Green dev `b81651fad2ba9ee523d52a8e5617648c78ee39fe`；候选为包含本文的提交。无 Migration，现有单一 Head `20261116_0056`。
- 范围：复用商品库曾使用的 Python 纯算，替换受控开关下的 Worker 类目预检签名；Worker、商品库、任务授权、店铺 Session 和其他签名调用不变。默认开关关闭，回退为关闭开关并重启 Backend。
- Feature 数据库：`control_center_feat_worker_pure_signer_v1`，独立空库初始化至 `0056`，应用角色不具备创建数据库、创建角色或超级用户权限。
- 验证：Backend 默认测试 764 项通过；Feature PostgreSQL 定向覆盖原授权边界、四种预检操作、纯算/原签名路径及 75 并发隔离。完整 Worker → 中控 → 商品库链路中的平台和商品库为测试替身，没有调用平台。
- 本机纯计算微基准：75 并发、750 次全部完成；此结果不代表生产吞吐或平台允许的并发。此前商品库 GET 类目树有真实平台成功证据；POST 的当前平台接受情况仍须结合真实运行结果核对，不能将模拟响应当作真实通过。
- 安全：不输出或保存 Cookie、完整签名 URL、正文或签名；GET 查询串和 POST 正文字节与实际请求一致。保留原 Session 的 `msToken`，不生成新值。
- 发布：先经 Gate 2、dev CI 和 main CI；纯算开关需经正式部署配置显式开启。旧签名服务暂保留以便切回；无需升级客户端或 Worker。
