# Worker 能力包与商品预检 V1 交接

范围：中控创建并分配预检，Worker 在本机读取已授权 RPA 店铺 Session，调用受限签名和抖店类目属性接口，将结果回传商品库。中控不创建或绑定店铺，不保存本机 Session。设备级 `all_mapped_shops` 默认关闭；显式开启后，该设备经 RPA 报告且浏览器状态为 `true` 的抖店自动进入轮转。精确店铺授权可用于收窄。

## 发布准备

- 仅受保护的发布环境保存 Ed25519 私钥；Worker 发行包只嵌入 32 字节公钥的 Base64 文件 `capability-public-key.txt`。正式公私钥尚需由发布负责人生成、受保护登记；测试密钥不得用于正式发行。
- `scripts/build-worker.ps1 -CapabilityPublicKeyFile <受保护位置>\capability-public-key.txt` 构建 Worker 0.5.0。普通安装启动自动读取包内公钥；不要求用户逐台配置环境变量。底座本身需安装一次，之后能力包可通过受信签名清单更新。
- 用 `worker/tools/publish_capability.py` 离线发布 `worker/capabilities/douyin_category_schema/capability.py`；服务端发布目录包括 `manifest.json`、64 字节原始签名 `manifest.sig` 和 `packages/<sha256>.zip`，服务器不持有私钥。后续签名清单使用递增 sequence，新增 skill 使用固定 `capability.py` 与 host API 1；本版入口是单文件能力，不提供任意任务命令或路径。
- 给清单的 `rpa_helper_sha256` 登记最终 RPA 发行物中 `win-unpacked/resources/listing-worker` 的完整目录摘要，不能使用事后变化的中间构建目录或单个 EXE 摘要。需复核安装包实际内容并按需要同时保留旧版本摘要。Worker 只把同用户 RPA marker 当作发现信息，独立校验固定位置和已签名整树摘要；浏览器未打开或状态未知不分配预检。
- Backend 需配置受保护的 `application_worker_precheck_clients_file`、单独开启 `application_worker_precheck_enabled`，以及提供受保护的 `worker_capability_package_dir` 和现有 Signer 配置。商品库凭据明确授权设备和可选的设备级全部映射店铺；旧 `application_shop_session_enabled` 可保持关闭。应用端及 Session 签名链必须使用经过校验证书的 HTTPS。

集成前置使用既有 Integration 人员及其团队：通过正式 `POST /api/v1/devices` 创建专用测试设备，再通过 `POST /api/v1/devices/{device_id}/worker-credential/issue` 一次性签发设备 Token，直接交给受保护启动器；不得记录 Token。独立商品库应用使用随机凭据，其 SHA-256 写入受保护授权文件；以下仅为字段示意：

```json
{"version":1,"clients":[{"client_id":"pdc-integration","token_sha256":"<凭据的SHA-256>","authorized_by_user_id":"<Integration超级账号UUID>","enabled":true,"shop_ids":[],"worker_precheck_enabled":true,"device_ids":["<测试设备UUID>"],"all_mapped_shops":[],"device_shops":[{"device_id":"<测试设备UUID>","local_shop_id":"<RPA本机店铺ID>","platform_shop_id":"<对应平台店铺ID>"}]}]}
```

单店验收使用上面的精确店铺授权；若后来明确授权设备全部映射店铺，将该设备 UUID 放在 `all_mapped_shops` 即可，不必逐店添加记录。不得改动既有 Integration 团队、人员或店铺数据，也不得使用生产凭据。

## 处理边界

- 中控幂等键为 `(client_id, product_id, revision)`，同版本新 attempt 仅继续查询原任务；不同参数冲突返回 409。结果按同设备、同任务接收；LOST 可等待原结果补传，新 revision 已存在时旧结果不覆盖。Worker 结果落盘后断线只重发结果，不重做平台请求；执行中崩溃且结果尚未落盘仍为未知。
- 本版只通过 Worker 授权的当前任务签名固定 `getSchema`，不提供通用 HTTP 代理。原始响应最多 3 MiB，受限业务 `items` 最多 4 MiB，结果封套额外最多 16 KiB，超限明确失败，不截断。仅返回商品类目属性必需字段和安全业务码，不返回 Cookie、Token、签名、完整 URL 或原始响应。
- Migration `20261110_0050` 基于 `20261020_0049`，新增本机店铺快照和应用预检幂等关联。降级仅允许已登记的 Feature 数据库且新表为空；有事实时保留，不能通过降级删除审计数据。

## 验证与尚待集成

Feature 库 `control_center_feat_worker_capability_precheck` 已从空库升级至 0050。定向验证覆盖同版本并发去重、两店顺序及并发轮转、结果丢 ACK 后补发、LOST 结果补传、旧 revision 防覆盖、设备与旧 Session 授权隔离、签名目标约束、字符串业务码、真实脱敏样本投影及大于 64 KiB 结果。合成 HTTP 链使用真实 PostgreSQL；RPA 会话、签名和平台响应均为替身，不代表真实平台成功。

RPA 对接候选 `3f4052fe3ec68034e0150e2078ac7ba51b236243` 提供 `browserOpen` 三态；商品库对接候选 `527a15ee5642984b1370c081d1a9ea836462a7cb`。Gate 2 使用隔离 RPA 候选树及 Integration 凭据、受信 HTTPS 和隔离商品副本，限制一机一店一商品、最多一次平台 HTTP。旧 RPA 无 marker 的测试启动器只在内存注入经核准的 `RpaLocalBridge`；正式 RPA 新安装自动写 marker 仍需另行实机验证。隔离启动器如用原 `sign_once.js` stdin 签名，须注明是真实签名算法、并非独立 Signer HTTP 部署链路。
