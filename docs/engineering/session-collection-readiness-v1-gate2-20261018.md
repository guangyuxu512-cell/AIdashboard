# ShopSession 采集就绪规则与关键 Verify Gate 2

## 结论与范围

- Feature Candidate：`0cede85d84bd2a5a699382479cb6fccfb0996c00`。
- Green 基线：`a445981f2c867f4d3fc01aaecf03960479209e87`。
- Integration `--no-ff` merge：`01b2d70fe5c01a1a4bd05ed23244ed830fd9ba0f`。
- 本次只统一服务器采集前的 ShopSession 就绪判定，并补 ShopSession 与选品品牌关键 Verify。
  没有 UI、Schema、Migration、依赖、运行配置、0047 商品实现或经营调度变化。
- 本 Gate 不连接数据库、Signer、平台、Electron 或生产；既有 5180/8100、
  `control_center_integration` 0047、商品预览与 Profile 均保持不变。

## 独立审查

ca97 逐文件审查 Candidate 与基线差异，确认：

1. `classify_collection_readiness` 是无解密、无写入、无平台 I/O 的纯判定，明确区分未配置、
   需权威验证、可用和需重新登录；Cookie `expires_at` 不再被当作本地硬失效门禁。
2. `bind_collection_auth_context` 同时绑定 Shop、平台和 Session 版本，健康检查后发生版本变化时
   显式拒绝旧上下文。
3. 选品和经营两个真实消费者都先显式调用一次 `ShopSessionHealthService.check(force=False)`，
   再绑定同一上下文；分页和 basic_info 不逐页追加身份请求。
4. 只有 Connector 明确返回认证失效时，才以版本 CAS 标记当前 Session 为 invalid；新版 Session
   赢得竞争时不会被旧请求覆盖。网络、Signer、解析和一般业务拒绝保持原分类，不误伤 Session。
5. Verify 新增 ShopSession Status/Metadata 的后端权威到 PC 真实 DTO、ViewModel 和状态映射检查；
   品牌 wire 期望独立固定为当前 `all=-1 / known=1 / unknown=0`，并保留 v7/v8 旧映射 Reader。
6. `scripts/verify/known-differences.json` 没有修改；SHA256 仍为
   `4ddacab88bc5a67737a024138ef9f487d6d536b48944092c46ab8ac79258c86b`。

未发现需要退回 Feature Owner 的业务 Bug、契约缺口、Migration 问题或越界改动。

## ca97 独立验证

| 检查 | 结果 |
| --- | --- |
| Session／选品／经营定向 pytest | 62 passed |
| Backend 完整离线 pytest | 899 passed、378 integration deselected、1 条既有 deprecation warning |
| 改动 Python 文件 compileall | exit 0 |
| `git diff --check` | exit 0 |
| Node 24 / pnpm 11 默认 `verify` | exit 0；28 known、0 new failure、0 stale |
| `verify --strict` | 预期 exit 1；仅同一 28 项 failure、0 stale |
| `verify --full --only=backend` | exit 0；899 passed、378 deselected；28 known、0 new、0 stale |
| 负向检查器自测 | 故意交换品牌 known/unknown 的子进程返回非零；新增服务端状态而消费方未同步同样返回非零 |

本机安全报告位于 ignored `.codex/`，不提交仓库：

- 默认：`cc8d465f673cf7a7f304fc7377c8830e08b413edced038d2868c7afcc3f42f1b`。
- strict：`af1ee457e5e6d953950f2f339d13421571478877068b38f45dfd5372952e365a`。
- full backend：`4318a1f691f2c077f96625025158ecbb3a19e525673768fb27f565ee0a8282dd`。

## 合后与交接

- 合后需复跑定向测试、默认 Verify 与仓库 CI；CI 成功后才把精确 dev SHA 标记为共享 Green。
- 本任务没有生产部署授权，不合 `main`、不发布、不修改生产或 Integration 运行配置。
- 得到精确共享 Green 后，7d55 必须在商品分支以正常 `--no-ff` 同步，并让商品消费者调用同一
  HealthService + binder；不得复制局部 `VALID + validated_at` 判定。商品 17 指标／DTO／状态 Verify
  与商品真实闭环仍由 7d55 独立完成、独立 Gate。

