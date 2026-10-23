# 手机商品采集 P3 评论图域名返修

## 范围和失败证据

Owner 81a1 在原 `feat/mobile-product-collection-integration-v1` 从精确父提交
`9ec5f1376c209942a244b9e55d9882f0167fd6d8` 正常追加本地候选，交回 ca97 独立 Gate 2。
此前全部签名、原包接收、清洗入库和 Real UI 成果保留，不回退分支、不改已应用的 0049。

ca97 报告第二次正式单机单商品任务已抵达 Integration，但返回 HTTP 422 /
`PRODUCT_COLLECTION_PAYLOAD_INVALID`。本机离线核验其受保护新包：836,237 字节，SHA-256
`e544b9f48878f72769cd43fba7c5f40f6e435d996e7e2218784e9b221fc5d217`。9ec5 parser 恰好拒绝一处：

- 字段：`detailBody.chunks[].promotion_v3.components[].slices[].data.item_list[].image.url`。
- HTTPS host：`p3-ecom-commentpic-sign.byteimg.com`。
- 资源路径前缀：`/douyin-user-image-file/`。
- 完整 query key 集合：`lk3s,x-expires,x-signature`。

先前媒体位置在本包中已通过。上述为当前新包证据，不沿用旧 gateway_delivery 认证失败作为当前阻塞。
真实原包只读取 ca97 的 ignored 文件，未输出/提交 URL 值、query 值、原始响应或凭据。

## 最小差异

运行代码只有 `media_urls.py` 一行：将该精确字段/资源前缀的 host 从单独 p9 改为已取证的 p3、p9 集合。
未引入 `p*` 通配，不改 query 规则或任何其他 URL 字段。HTTPS、443、无 userinfo/fragment、完整 key
集合、非空签名、重复/编码后重复键、额外 query、未知 host/path、明文及嵌套身份的原拒绝规则保持。
`comments[]`、request URL、SKU、历史 V1、假数组或带点字段仍不能取得该例外。

测试沿用既有缩小 fixture，增加 p3 正例和原值/hash 保留断言、p3 的同等严格 URL/身份负例与上下文隔离。
原“未取证 p3 应拒绝”样本现转为已取证正例；未知域名负例改为 p6，拒绝断言保留。所有 URL/签名值均为
明确的合成值。Backend 文档 27 同步精确媒体表，未重写解析流程或 cleaner，API、DTO、Frontend、Migration 不变。

## 本次验证

| 检查 | 实际结果 |
|---|---|
| 修前新包 parser | REJECTED，精确 1 处媒体 URL；源文件未改 |
| 修前新增正例回归 | 2 FAIL / 4 PASS / 154 deselected；拒绝点与真实包一致 |
| 修后 Product Collection 非 PG | 160 PASS，5.42s；使用原 ignored 隔离 launcher，无 `.env`/端口/后台消费者 |
| strict 及 Backend 离线 profile | Node 24 + 已安装 pnpm：`pnpm verify --strict --full --only=backend --report=.codex/mobile-product-collection-ecom-p3-20261023/verify-strict-backend.json`；exit0，1241 PASS / 481 deselected，94.02s；known/new/stale 全0；Node10/AST2/Frontend契约9通过 |
| 本次新包原 parser 到既有 cleaner | ACCEPTED；7 SKU / 12 主图 / 18 详情图，商品身份匹配，detailBody/skuBody/三个源 hash 保留 |
| 原值保护 | 文件字节/hash前后相同；规范化内容 hash 为 `9d68cbf250c12da7c0941f0163f0bc272efaebdf714d4a7a69d275d8dc55e625` |
| 静态检查 | 两个 Python 路径 compileall、`git diff --check` PASS |

只保留既有 Starlette/httpx deprecation warning。原运行 profile 明确排除 PG、开端口的 Signer/Webhook
用例和其他端完整套件，不能把 deselected/NOT_RUN 写为通过。本轮未连数据库、执行 Migration 或真实
HTTP 上传，未更改 Integration/生产、开关、失败任务、手机或 NAS；未部署、push、运行 Hosted CI 或合 dev/main。

## 交接和验收边界

本地新 Candidate 与完整 SHA 见正式 Handoff。ca97 应独立复核同包，再沿原 Gate 2 流程替换 Backend
精确版本；Real UI 保持 `a28bbe8d07163c52fbcb8d05f4fe65d076bd1646`，手机/NAS 对照仍为
`f81f350ab143f2e01a9ecfe34432136087170907`，实际设备版本以其现场记录为准。

离线 parser/cleaner 已通过不等于新 Candidate 的真实 202、入库和终态回调已通过。完整实机闭环仍待
ca97 验收，失败任务与真实包保留，本修复不授权自动重试。Owner 不改8100/5180或生产。
若需回退，只正常 revert 本增量，不删除/改写历史包、失败项或 0049。新 SHA 未扩大先前仅针对
bad155c/a28bbe8 的推送授权。用户未提交 `AGENTS.md` 与 `docs/engineering/history/` 保留、不纳入候选。
