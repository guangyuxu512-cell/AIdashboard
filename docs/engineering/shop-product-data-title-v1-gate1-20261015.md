# 商品数据标题单行与 ID 标签返修 — Gate 1

本记录保留7954c434edcfd8dd14ad15d7a8a2ee67899087e8阶段事实。
后续仅追加复制按钮对齐，见 shop-product-data-copy-alignment-v1-gate1-20261015.md。
用户对已有视觉的认可不代表该追加改动或整个商品数据模块验收通过。

2026-10-15，Owner 7d55；在 feat/shop-product-data-frontend-v1 上接续
05f1d25d992054c28d1bcc52562e378dc28fc807，不切分支、不改写历史。
本记录仅是用户两项预览返修的技术交接，不代表原候选或整个商品数据模块人工验收通过。
新候选为包含本记录的 Feature HEAD，完整 SHA 见最终回执和本地 preview manifest。

## 最小修改与原因

- ProductInfoCell 原先显式使用 NEllipsis line-clamp=2，长标题形成两行并增加整行高度。
- 移除两行设置，直接复用现有 NEllipsis 默认的 nowrap / ellipsis / 溢出悬浮全文。
- 编号独立一行显示“ID：<商品ID>”；复制逻辑仍直接写入原 productId 字符串，
  不拼接前缀、不做数值转换。Unit使用21位字符串，浏览器验证19位末位为1的ID。
- 不改图片、ProductDataTable列宽、全局字体/样式、候选池布局或共享ShopSelector；
  不改Backend/DB/迁移/Worker/Electron。运行代码只有同一展示组件的两行变化。

测试配置新增3个视口用例，并允许通过 PRODUCT_DATA_REUSE_PREVIEW=1 显式复用本工作树
已登记的Mock 4177；默认不复用，Real始终不复用，避免测试终止现有人工预览服务。

## 实际验证

先在原05f页面复现：1024×768、1440×900、1920×1080均为2行，3个新单行断言失败；
修复后同一组件和实际浏览器全部通过。未通过扩大列宽或放松行高断言解决。

| 视口 | 标题行数 | 长标题行/短标题行高 | 缩略图 | 结果 |
| --- | --- | --- | --- | --- |
| 1024×768 | 1 | 81px / 81px | 64×64 | PASS |
| 1440×900 | 1 | 81px / 81px | 64×64 | PASS |
| 1920×1080 | 1 | 81px / 81px | 64×64 | PASS |

三处均验证：nowrap、ellipsis、标题限制在当前容器、悬浮全文可见、ID独立一行、
“ID：”展示、纯ID复制/粘贴回读一致、页面无横向溢出。列配置360px不变；
最大化时现有表格按剩余空间分配到约420.61px，未改任何列配置或扩宽逻辑。

- Vitest定向：ProductInfoCell、ProductDataView、CandidatePool、CandidateDetailDrawer，
  4文件 / 20项 PASS，覆盖字符串ID、既有图片重试/尺寸及页面流程。
- Mock Playwright：新增三视口 + 既有候选图/商品数据全流程/错误恢复，6项 PASS。
  另重跑三视口以保存无悬浮层的清晰截图，3项 PASS。
- lint PASS；build 内 typecheck PASS；production Real build PASS（既有大chunk提示保留）。
- 本次按两行展示改动执行定向回归；未把之前692项完整回归写成本次重新执行。
- 单行修复后首次悬浮断言误用库未提供的 tooltip role，截图已实际出现全文；
  改为定位现有库的可见 .n-tooltip，并保留全文与几何断言，之后通过。

命令：

    pnpm --filter @control-center/frontend exec vitest run src/entities/product/ui/ProductInfoCell.spec.ts src/features/product-data/ui/ProductDataView.spec.ts src/features/product-selection/ui/CandidatePool.spec.ts src/features/product-selection/ui/CandidateDetailDrawer.spec.ts
    pnpm --filter @control-center/frontend lint
    pnpm --filter @control-center/frontend build
    pnpm --filter @control-center/frontend exec cross-env PRODUCT_DATA_REUSE_PREVIEW=1 playwright test --config playwright.product-data.config.ts --output=test-results/product-data-title-v1
    pnpm --filter @control-center/frontend exec cross-env PRODUCT_DATA_REUSE_PREVIEW=1 playwright test --config playwright.product-data.config.ts e2e/product-data-title.spec.ts --output=test-results/product-data-title-v1-display

## 预览、截图与接续

复用7d55唯一 http://127.0.0.1:4177/#/product-data，Mock、strictPort；
本次未重启或替换其他环境服务/Profile，不启动Electron。
截图在 frontend/test-results/product-data-title-v1-display/ 下（已忽略）：

- product-data-title-keeps-l-13ae4--titles-on-one-line-at-1024/single-line-title-1024.png
- product-data-title-keeps-l-8d0f7--titles-on-one-line-at-1440/single-line-title-1440.png
- product-data-title-keeps-l-ecd27--titles-on-one-line-at-1920/single-line-title-1920.png
- 各目录同时有 single-line-title-tooltip-<视口宽度>.png，显示完整悬浮标题。

原复现证据在 product-data-title-v1-before/，既有回归证据在 product-data-title-v1/；
均为虚构商品，不含Token/Cookie。

ca97接续：核对精确新候选与上述当前预览，确认单行、省略/全文、ID标签与纯字符串复制，
普通/窄窗口及最大化视觉；不得将旧05f当作用户通过或混入81a1选品修复。
本次Gate 1通过；ca97对新候选Gate 2、真实Electron与用户人工确认仍未覆盖。
没有部署、发布或安装包变动，仍停在“待用户验收，禁止发布”。
