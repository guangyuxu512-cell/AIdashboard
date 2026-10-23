# 手机商品资料：生产采集路径最小对齐与 CDN 返修

## 候选与范围

- Owner：81a1；`feat/mobile-product-collection-integration-v1`。
- 直接父提交 `ac1af52d417879437237e8411d637d2cf9d509af`；本次新 Candidate 以交接回报的完整 SHA 为准。
- 运行代码只增加三个有真实样本的精确媒体 host，保留原字段/协议/path/query/认证安全判断；没有修改
  Dispatch、HMAC、Inbox/Outbox、cleaner 算法、商品版本/来源、权限、Shared、UI 或已应用 0049。
- 独立 `AGENTS.md` 清理 dirty 与 `docs/engineering/history/` 原样保留且不提交；没有在 AGENTS 写进度。
- 外部配对参考是只读网关 `e4f19b9bb3e6546947d7dcd26586892ccac62a69`，不是在用生产版本的声明。

## 新 422 的离线证据与修复

97 在当前 ac1 运行实例核对了同一保留原包，中央报
`PRODUCT_COLLECTION_PAYLOAD_INVALID / Complete package contains a credential-bearing URL`。本轮没有重采。

| 保留原包 | 字节数 | 修前正式 parser | 修后 parser → 现有 cleaner |
|---|---:|---|---|
| SHA-256 `22f3a102553770672a3cf39aa6c32b8e1a11c585d47ae2f8738fb6372782f301` | 829681 | 接受 | 19 SKU / 8 主图 / 5 详情图 |
| SHA-256 `ac27be487636edb08908093ff00df4a766fb1aed584d8c0dc2a3f1ab3a70cc64` | 830165 | `detailBody` 认证 URL 误拒 | 19 SKU / 8 主图 / 5 详情图 |

第二包有八个视频 URL 使用 `api-play-hl.amemv.com` / `api-hl.amemv.com`，仍在原
`play_opt_model.play_addr/play_addr_lowbr/play_addr_h264/bit_rate[].play_addr.url_list[]` 位置，path 仍为
`/aweme/v1/play/`、query 名仍为 `video_id/file_id/line/is_play_url/sign`。另两个图库 URL 使用
`p11-sellpoint1-sign.byteimg.com`，仍在已支持的 bubble avatar/icon 图片位置，query 名仍为
`rk3s/x-conf-key/x-expires/x-signature`。只补这三个精确 host，不开放域名通配符。

两原文件在验证前后 SHA-256 相同；全部已提交字段和值保留、既有默认值规范化不变，三个 Collector hash
继续严格校验格式。第二包规范化 content hash 为
`6fe8ecc267fffe597be724155ede35c4da6ce72606f0d71abb4b461e97a95373`；不把该值与文件字节 hash 混用。
两个商品身份均匹配原任务上下文；展示 `primary_image_url` 仍经原净化逻辑删除 query。未下载媒体、
未把原包/URL 查询值/凭据保存到 Git 或报告。安全离线证据在本树 ignored
`.codex/mobile-media-production-alignment-20261021/both-samples-proof.json`。

## 接口与地址矩阵

**唯一真机路径为生产 NAS `192.168.0.102:3602`，管理端 `:3600`。** 不建立其他手机采集通道，
不使用旧隔离网关。设备操作只归原手机项目；有效 LSPosed 持久凭据/配对/APK 保持，旧 401 影子文件不能
作为重建依据。Watchdog 兼容回退和旧待发包外键错误保持独立，不删包、清真实队列或改状态绕过。

| 环节 | 正式方法/路径与身份 | 代码对齐与当前运行证据 |
|---|---|---|
| 手动商品 ID / 候选池提交 | 中央 `POST /api/v1/product-collection/requests`；Human Session/Team，既有 manual.targets / selection_candidates.candidate_ids | 两来源继续共用现有 Service/API，不新建入口或任务机制；当前8100 OpenAPI含此POST |
| 中央派发生产网关 | `:3602 POST /api/v1/jobs`；独立 control dispatch 服务身份；`central_ingest_v1`、稳定 external ID/hash、冻结 maxAttempts | 中央 Gateway Adapter 与 e4f 的中央任务 DTO 对应；**97确认当前8100仍指向旧3616，尚未切到生产**，本Owner未修改地址 |
| 手机采集/原包上传 | `:3602 POST /api/v1/device/jobs/claim`、`POST /api/v1/device/mobile-captures`；原 Device 身份 | 手机原入口与原采集/自动化不改；生产 `/health` GET200、管理首页 GET200。新中央任务的生产能力、身份、原有协议授权由原手机项目只读确认 |
| 网关注册/续发 | 可达中央 `POST /internal/mobile-collection/v1/attempts/register`、`POST /internal/mobile-collection/v1/attempts/{attempt_id}/credentials/refresh`；gateway service 身份 | e4f 请求字段与中央契约对应；当前8100 OpenAPI两POST存在。Gateway只持久化绑定元数据，服务内取得 credential，不下发手机 |
| 网关转发完整原包 | 中央 `POST /api/v1/mobile-collection/ingest/{attempt_id}`；绑定 Job/Device/Batch 的短期 credential | e4f 先按原路径保存本地包，再服务端转发中央，校验202及匹配 receipt；中央并未要求手机换直传地址。当前8100有接口但仍为旧ac1，会拒第二包，必须加载新候选复验 |
| UU/版本入库 | 中央 Inbox → 原 `ExistingUuProductPackageCleaner` → Version/Product/Persist Receipt短事务 | 新两份原包离线19/8/5通过；本轮无新实际 Receipt/Version/业务事实，不把离线清洗称为入库成功 |
| 最终结算 | 中央 → `:3602 POST /api/v1/control/collection-settlements`；独立 callback 服务身份，匹配 Job/Device/Batch/attempt/receipt | 字段、状态、错误分层沿既有配对契约；生产是否已部署并启用该能力/回调配对尚待原手机项目核验，健康200不能证明此POST可用 |
| 正式结果读取 | 中央 `GET /api/v1/product-collection/requests/{request_id}`、商品库现有GET | Team/权限过滤、当前版本/历史读取保留；当前8100商品库GET在schema中，实际新结果须97后续验收 |

只读 HTTP 实际请求仅四次：生产 API `/health`、生产管理首页、当前8100 `/health` 与 `/openapi.json`，均200；
没有以探测为名调用 POST/PATCH/claim/上传。中央健康返回 `{status:ok}` 不是数据库和所有配置已通过的证明。
运行事实与源码承诺分开：当前中央运行 ac1 由97核定，本次源码未加载；生产网关确切镜像/源码版本、
中控适配开关、服务身份和可达回调由原手机项目核对，本Owner不读取/代改其凭据或部署。

## 必要配置名（不含秘密值）

- 中央出站/回执：`BACKEND_PRODUCT_COLLECTION_GATEWAY_BASE_URL`、`BACKEND_PRODUCT_COLLECTION_GATEWAY_ID`、
  `BACKEND_PRODUCT_COLLECTION_GATEWAY_CONTROL_TOKEN`、`BACKEND_PRODUCT_COLLECTION_GATEWAY_CALLBACK_TOKEN`。
- 中央接收：`BACKEND_PRODUCT_COLLECTION_SERVICE_TOKEN`、`BACKEND_PRODUCT_COLLECTION_INGEST_HMAC_KEY`、
  `BACKEND_PRODUCT_COLLECTION_INGEST_KEY_ID`、`BACKEND_PRODUCT_COLLECTION_PUBLIC_BASE_URL`。
  回调/upload origin 必须从生产网关可达，不能用NAS自身loopback代替中央地址。
- 中央三阶段：`BACKEND_PRODUCT_COLLECTION_EXECUTION_ENABLED`、`BACKEND_PRODUCT_COLLECTION_PROCESSING_ENABLED`、
  `BACKEND_PRODUCT_COLLECTION_SETTLEMENT_ENABLED`；`BACKEND_PRODUCT_COLLECTION_CLEANER_MODULE_PATH`、
  `BACKEND_PRODUCT_COLLECTION_IMAGE_ALLOWED_HOSTS` 保留原受保护配置。
- 单次真机 `BACKEND_PRODUCT_COLLECTION_CAPTURE_MAX_ATTEMPTS=1`，在新 Dispatch 生成前冻结；
  中央网络重放复用原任务，不扩大手机 capture 预算，普通 retry不能重开耗尽的单次Job。原正常预算3和显式重采保留。
- 网关：`CONTROL_INTEGRATION_ENABLED`、`CONTROL_BASE_URL`、`CONTROL_GATEWAY_ID`、
  `CONTROL_DISPATCH_TOKEN_FILE`（对应中央出站 control token）、`CONTROL_OUTBOUND_TOKEN_FILE`
  （对应中央 service token）、`CONTROL_CALLBACK_TOKEN_FILE`（对应中央 callback token）。
  可选原路径/超时配置 `CONTROL_ATTEMPT_REGISTER_PATH`、`CONTROL_ATTEMPT_REFRESH_PATH`、
  `CONTROL_HTTP_TIMEOUT_MS`、`CONTROL_ALLOW_INSECURE_HTTP` 仍遵循既有实现，不能以放宽认证绕过差异。

不输出这些配置的实际值/密钥或服务器环境全文，本轮没有修改任何运行配置。

## 定向验证与边界

- 修前新增精确CDN正向用例10失败，其他45通过；修后媒体55全部通过，包含六个新增安全反例。
- 使用仓库既有 `isolatedEnvironment`、空配置工作目录运行 Product Collection 非PG：**120 passed**。
  认证、终态、哈希/批次绑定、预算冻结/重放、正常有限重试等定向覆盖保留；没有平台调用。
- 第一轮从本机Backend目录启动的单测未及时完成，未计通过；仅核对并停止本轮pytest launcher/child，
  没有停止8100等服务，随后用空配置目录重新验证。没有为此修改运行源码、调度器或公共测试框架。
- 两份原包均正式 parser→现有 cleaner，通过19/8/5；文件/字段/身份/展示净化检查通过。
- `compileall` 与 `git diff --check` 通过；Node24.19/pnpm11.25 `pnpm verify --strict` exit0，
  0 known/new/stale，负向自测、ASGI与9个客户端探针通过，未安装包/改依赖。
- 未受影响的 ac1 FeaturePG6、Backend1189 和既有配对记录按源码不变范围复用，**本轮未重跑PG/全Backend**，
  不把这些旧结果当成当前生产或新真机闭环。
- 修改只在 `media_urls.py`、对应单测、后端契约及本交接。没有新Migration、数据库写入测试、UI/Shared/
  手机/APK/网关代码变化，没有push/PR/GitHub CI、dev/main合并或部署。私有库需CI时先按要求告知安排。

## 下一负责人及上线停止点

1. 规划将精确新候选交97独立源审；97按既有实例管理加载新中央候选并确认实际代码，保留同一前端入口/
   登录，不重复未变的整轮人工验收。中央仍运行ac1时不得把新离线通过写成运行422已修复。
2. 原手机项目确认在用`:3602`是否已经包含e4f必需服务接口及既有协议授权，核对网关身份/双向认证/
   可达回调；97核对中央出站仍旧3616这一明确差异。不代改设备分配、配对、凭据或服务器配置。
3. 若生产缺少必需适配，先列精确缺口并走各自正式发布流程。网关适配只在原生产服务生效；中央生产若
   需0049，由Main在Release Gate、备份/恢复检查后处理，不能改写迁移或借测试授权提前上线。
4. 双端匹配和适用发布/配置步骤通过后，使用人类已授权的一次测试，由原手机项目控制设备、97走现有
   正式入口提交一个新任务；claim前确认新Gateway Job的`maxAttempts=1`且没有自动capture重试。
5. 逐一对应新Request/Item/Dispatch/Gateway Job/Batch/Attempt → Raw receipt → Product/Version/Persist
   Receipt → Gateway settlement → API/Real结果。只有这一链条自然成功才能通过；不上传旧包冒充新采集，
   不手工补业务记录、删旧包/任务或强行改成功。原商品旧版本/来源历史及新失败证据保留。

本轮Owner交付为最小本地候选及对齐记录；实际生产端适配、授权配置和一次真实闭环仍待上述责任人完成。
本聊天回报供规划转交，不自行跨聊天下发、代做集成或发真机任务。
