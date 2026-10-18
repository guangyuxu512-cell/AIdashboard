# 商品数据成功空结果保留表头 Gate 1

## 结论与基线

- 分支：`feat/shop-product-data-empty-header-v1`。
- 起点为最新 Green `origin/dev`：`d13d00fad08c44ba4cbb415e34769cfeac196632`；对应 CI
  `39088873660` 四项全绿。
- 仅消费 ca97 已独立 Gate 2 接受的 Shared Candidate：
  `69f345a5350932a5e0ae87a9ebb619e8cc1515be`，通过正常 `--no-ff` 合并，合并提交为
  `6ac5236c003f45a7bbc8dbcd3fed61a2ce7efa7b`。未修改该 Shared Candidate。
- 最终 Product Candidate 以正式 Handoff 报告的完整 SHA 为准。本次不是生产发布授权。
- 没有 Backend、API DTO、数据库、Schema、Migration、平台采集、Session、Electron、Worker、依赖或
  运行配置改动。

## 根因与最小修改

商品数据消费者把成功空数组传给 Shared `DataTable` 后，旧默认行为会用独立 `EmptyState` 替换整个
`AppTable`，因此 `<thead>` 不存在。原商品组件单测整体 stub 了 `DataTable`，原浏览器回归只断言空文案，
两者都没有检查真实表头，因而未发现该状态与字段配置语义不一致。

本次只在 `ProductDataTable` 显式启用 Shared 的 `showHeaderWhenEmpty`：

1. 首次成功查询无数据和筛选无结果时，保留固定商品信息／操作列及用户已保存的可见字段和顺序；空文案
   仍位于表格内容区，不创建占位商品行。
2. Loading 与 Error 仍优先显示原独立状态，不显示表头，也不伪装为成功空结果；重试成功后恢复真实表格。
3. 值为 `0` 的商品仍作为正常数据行显示；有→空→有不改变字段顺序、固定列或横向滚动语义。
4. 仅开发态 Mock 接受精确 `productDataPreview=empty-success`，用于首次成功空结果的浏览器回归；Real
   构建不读取该夹具，普通 Mock 仍生成 31 条数据。

共享组件保持默认关闭，其他消费者行为不变；没有新增通用表格或空状态框架。

## Gate 1 实际验证

| 检查                          | 实际结果                                                                              |
| ----------------------------- | ------------------------------------------------------------------------------------- |
| 先红后绿定向组件测试          | 实施前真实渲染用例得到表头 `[]` 并失败；启用参数后 `ProductDataTable` 3/3 passed      |
| 商品 Source + Table 定向      | 2 files、19 tests passed                                                              |
| 商品 Vitest 与契约            | 15 files、138 tests passed                                                            |
| 首次空结果定向浏览器回归      | 4/4 passed；真实 `<thead>`、保存字段顺序、0 行、空文案、横向滚动和 `共 0 条`          |
| 商品 Playwright 完整配置      | 26/26 passed；覆盖 1024/1440/1920、四种主题、字段拖拽、筛选、分页、弹窗及 Error→Retry |
| PC 完整单测                   | 169 files、924 tests passed；保留既有 jsdom 外链图片 `AggregateError` 警告            |
| PC lint / typecheck           | 均 exit 0                                                                             |
| Real production build         | exit 0、5805 modules；仅既有大于 500 kB chunk warning                                 |
| Prettier / `git diff --check` | TS/Vue/E2E 与新 Gate 记录 check passed；diff check exit 0；既有契约文档保留原表格格式 |
| 测试端口                      | Playwright 使用既有获准端口 4177；结束后无监听                                        |

Shared `DataTable` 定向与完整 PC 测试中的 `n-config-provider` 提示来自已接受 Shared Candidate 的既有直接
mount 测试，本次商品消费者没有新增该提示。浏览器截图与 Playwright 中间产物保持本地 ignored，不提交。

## Verify 说明

- 首次从系统 Node 20.18 启动时，pnpm 11 因要求 Node 22.13 以上并缺少 `node:sqlite`，在正式检查前退出。
- 改用工作区已配置的 Node 24 后，默认 Verify 与显式 `CI=true` 均完成检查，但以
  `24 known + 4 stale`、exit 1 结束。四条 stale 均是 Green 已登记的既有 runtime-contract：
  `mobile:ECONNABORTED`、`mobile:ERR_CANCELED`、`pc:html-200`、
  `pc:enterprise_account:null`。
- 本分支相对 Green 没有修改 `scripts/verify`、`known-differences.json`、PC 公共请求、Mobile 或设备 mapper；
  没有通过改例外清单掩盖本机分类漂移。
- 同一精确 Green SHA 的 CI `39088873660` 中，上述四项连同其他 24 项均被识别为
  `KNOWN NOT FIXED`，Verify 以 `known-not-fixed=28`、exit 0 完成；四个 CI job 全绿。因此本机 Verify 不记录
  为通过，而如实保留为与 Green CI 不一致的执行条件问题，交 Gate 2 复核。

## 未覆盖、回退与 Gate 2

- 未连接 Feature、Integration、Main 或生产数据库；未执行 Migration、真实平台请求、原生 Electron、
  安装包、Worker、容器、部署、生产 smoke 或人工生产闭环。
- 未修改或复测其他 `DataTable` 消费者；其默认行为由 Shared Candidate 的定向回归保护，本任务只验证商品
  消费者的显式启用。
- 回退只需正常回退 Product Candidate 和已记录的 Shared 合并；没有数据库、配置、凭据或部署恢复动作。
- ca97 Gate 2 需独立复核 Shared 精确 SHA 的消费、首次成功空结果、筛选空结果、Loading/Error 优先级、
  保存字段顺序、零值数据行、横向滚动、Real 构建隔离及 Verify 的本机/CI 差异，再决定是否合入 dev。
  不得自行合入 dev/main 或发布生产。
