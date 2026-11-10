# Worker 能力包与商品预检 Gate 2

- Candidate：`56a7ccde655a7bc92ccfa9695dbd32b6e26d2283`；基线 Green dev：`ef63e85bda0407a9dcfe64ac0db2cdc0791370ba`。
- PR 精确 SHA CI：[42835468970](https://github.com/guangyuxu512-cell/AIdashboard/actions/runs/42835468970)，Backend、Frontend、container-runtime 和 verify-offline 全部成功。独立临时 PostgreSQL 实际执行 9 项；Nginx 检查使用真实容器。
- Migration：`20261110_0050`，基于 `20261020_0049`。Integration 已升级；两张新增表用于设备映射和预检任务关联。生产发布必须先有可读的新备份，回滚关闭新路径并保留数据。
- Integration 真机：HuanYu 的本机 RPA Session 经正式 Worker 任务对商品 `3844324466901518182` 的已有类目 ID 完成一次只读预检，平台 HTTP 200、业务码 0，类目属性 26 项，结果写入隔离商品副本；测试使用原签名算法的隔离传输。
- 另按同一店铺做类目树只读诊断：根 42 项、子节点 15 项，均 HTTP 200、业务码 0。该诊断证明 Session 当前可用，不证明商品库手动类目树已经接入 Worker。
- 发布版 RPA `0.6.0-dev.75` 的安装包隔离首启、marker、helper 依赖和同机已登录 HuanYu 会话读取通过；未覆盖现有安装。签名清单信任的 helper 完整目录摘要由 `helper_tree_digest` 对实际安装包解出的内容计算。
- 正式 Worker `0.5.0` 包与正式公钥和离线签名清单已交叉验签；结果先落盘后进程中断、重新启动补传使用隔离故障注入验证。真实硬断网、带真实 BitBrowser API Token 的设备和生产整链未验证。
- 生产独立 Signer 使用无店铺会话的合成参数，对 getSchema 和 categoryOptionsN 均 HTTP 200 并生成签名；没有请求平台。不得将此等同于生产 Worker 真实业务闭环。
- 当前实现为本机请求平台；签名时通过 HTTPS 将本次 Cookie 临时发送至中控和内部 Signer，应用代码不主动持久化。新代理路径关闭请求体缓冲和访问日志。
- 发布范围仅为已有类目的自动预检；商品库手动类目树、搜索、推荐和手动属性查询仍走旧链路。正式授权、设备能力上报、商品库迁移和队列启用均由各自发布负责人完成后再认定生产可用。

Gate 2：本候选按以上范围接受；不得将候选 CI 或测试签名替代精确 dev/main CI、Release Gate 和生产核验。
