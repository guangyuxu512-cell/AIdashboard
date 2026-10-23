# 手机商品采集签名媒体兼容返修

## 候选范围

Owner 为 81a1，下一责任人为 ca97 独立 Gate 2。在原分支
`feat/mobile-product-collection-integration-v1` 从已推送的精确父提交
`bad155c1c1f7b33fc194d2ad1b85ab09304fb47f` 正常追加；完整 Candidate 以交接回执为准。

本次只修复 Gate 2 原包中的两个已取证媒体位置：视频 cover 的新增资源路径，以及商品图卡
`item_list[].image.url`。不改原包接收入口、任务或凭据绑定、清洗算法、队列、数据库、Migration、
Real UI、手机自动化或 NAS。未重试原失败任务，未操作运行开关。

## 最新失败与复现

ca97 的当前真实证据为 OPPO、Automation 0.3.14、Collector 0.4.12、抖音商品
`3844324466901518182`、`max_attempts=1`。该次已成功 claim/register attempt，进入商品页并点击
购物车，生成带正确 Job/Batch/平台商品身份的 schemaVersion 2 完整包。
因此不能再把本次阻塞沿用为旧的 `gateway_delivery` 认证失败；当前可独立复现的是 parser 的媒体 URL 拒绝。

原包只在 ca97 本机被 Git 忽略的位置保留。本 Owner 离线读取的包为 833,995 字节，文件 SHA-256 为
`b3e8ed3360ac9e53005a7b51887761a3868bbae4cbd55e63702c425c829ed768`。旧 parser 拒绝精确 5 项：

| `detailBody` 字段（省略 `chunks[].promotion_v3`） | 域名与资源前缀 | query key 集合 | 数量 |
|---|---|---|---|
| `header_v2.cells[].multi_preview.cells[].cell.media.video.play_opt_model.cover.url_list[]` | `p3-sign.douyinpic.com`，`/tos-cn-v-800a60/` | `dy_q,l,x-expires,x-signature` | 1 |
| `components[].slices[].data.item_list[].image.url` | `p3-product-comment-sign.byteimg.com`、`p9-product-comment-sign.byteimg.com`，`/tos-cn-i-8y5sebgt5i/` | `lk3s,x-expires,x-signature` | 3 |
| 同上 `item_list[].image.url` | `p9-ecom-commentpic-sign.byteimg.com`，`/douyin-user-image-file/` | `lk3s,x-expires,x-signature` | 1 |

没有保存或输出真实 URL 值、query 值、原始响应、Cookie、Token 或原包内容。版本化夹具只复用上述
对象/数组布局与域名/资源前缀，资源名、签名、hash 等均为合成值，不复制真实原包。

## 最小实现与安全边界

唯一运行代码差异位于 `backend/app/modules/product_collection/media_urls.py`：

- 原 cover 规则保留，仅增加 `/tos-cn-v-800a60/` 前缀；新前缀要求上述完整 query key 集合。
- 另登记精确 `item_list[].image.url` 字段，分别绑定两个 comment host 与 `tos-cn-i` 前缀，或
  `p9-ecom-commentpic-sign` 与 `douyin-user-image-file` 前缀，不允许 host/path 交叉组合。
- 新例外要求 HTTPS、精确字段/host/path 及完整 query key 集合。所有规则继续拒绝重复键（包括编码后
  重复）、额外 query、空签名、未知 host/path、userinfo、非 443 端口和 fragment。
- 不扩大原 `comments[]`、video play、gallery 规则；不让新 ecom host 成为任意字段白名单。
  V1、SKU Body、request URL、伪造字典键/数组和明文/嵌套身份字段继续拒绝。

`backend/tests/test_product_collection_media_urls.py` 增加缩小五图完整包 fixture、四组独立正例及
字段/host/path/query/身份隔离负例；未修改原有断言或移除已有安全测试。协议表同步在 Backend 文档 27。

## 本轮实际验证

| 检查 | 实际结果 |
|---|---|
| 修前原包离线 parser | REJECTED，精确 5 个媒体 URL；不输出 URL 值 |
| 修前新增定向测试 | 5 FAIL / 18 PASS / 122 deselected，复现合法媒体被拒绝 |
| 修后全部 Product Collection 非 PG | 145 PASS，4.91s；复用 ignored 隔离 launcher，无 `.env`、端口或后台消费者 |
| 完整 Backend 离线及 strict Verify | `pnpm verify --strict --full --only=backend --report=.codex/mobile-signed-media-gate2-20261023/verify-strict-backend.json`，使用 Node 24 与已安装 pnpm；exit 0，Backend 1226 PASS / 481 deselected，97.13s；known/new/stale 全 0，10 Node / 2 AST / 9 Frontend 契约通过 |
| 当前原包 parser 到既有 cleaner | ACCEPTED；7 SKU / 12 主图 / 18 详情图；商品身份匹配 |
| 原包与字段保护 | 文件字节/hash 前后相同，detailBody/skuBody/三个源 hash 保留；规范化内容 hash 为 `3a90defc4892d34ce9da95c12f62450d12d44abc5033290db46cfcf1398cd2b3` |
| 编译和 whitespace | 两个 Python 变更路径 `compileall -q` 及 `git diff --check` PASS |

首轮修后测试的两个负例因断言只匹配 `credential` 而失败：实际分别被既有 scheme/userinfo 检查拒绝。
已按这三类明确安全错误修正测试消息预期，运行拒绝规则不变；最终 145 项全部通过。仅保留既有
Starlette/httpx deprecation warning。

本轮没有新增 PostgreSQL 验证或迁移；父候选的 Feature PG 5 项证据只作为未改事务路径的历史记录，
不算本轮新通过。未执行真实 HTTP 上传、手机/NAS 请求、消费者、Integration/生产数据库、Electron、
配置、部署、Hosted CI 或 dev/main 合并。Backend 完整离线 profile 排除的 runtime/PG 用例仍为 NOT_RUN。

## 交回 ca97

当前代码可交独立 Gate 2，整体手机直传闭环仍未通过。ca97 在其受保护样本上复核 parser 后，再沿已有
授权处理精确新 Backend、Real UI `a28bbe8d07163c52fbcb8d05f4fe65d076bd1646`、手机/NAS
`candidate/mobile-nas-control-ingest-v1` / `f81f350ab143f2e01a9ecfe34432136087170907` 的实际运行配对。
手机现场 Automation/Collector 版本仍以其本次证据为准，不因代码仓库 Candidate 推定设备已更新。

本次不重新组合前后端、不更改 0049，不把离线包解析和 cleaner 成功冒称真实 202/入库或 Electron 验收。
已应用 Migration `20261020_0049` 和原任务/失败历史均保留。ca97 报告的运行准备态为三消费者 false，
本 Owner 未修改或重新探测其服务。

新 Candidate 仅本地提交；前次人类推送授权针对 `bad155c…` / `a28bbe8…` 两个旧精确 SHA，本轮没有
将该授权扩大为新 SHA 的 push/PR/CI。ca97 可直接读取共享本机 Git 对象审查；需要远端推送时另行安排。
回退只需正常 revert 本次新增兼容规则及其测试/文档，不修改旧记录或删原包。用户独立维护的
`AGENTS.md`、`docs/engineering/history/` 不纳入此 Candidate。
