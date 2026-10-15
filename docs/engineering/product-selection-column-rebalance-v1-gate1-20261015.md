# 候选池三列宽度再平衡 — 增量 Gate 1

- 直接回读规划人类 turn `01a13e4f-984f-7802-a6c3-e54d5aa44e09`：610标题偏短，希望商品信息向右扩、回收店铺名与类目的留白。不是610视觉通过或发布授权。
- 沿 `feat/product-selection-candidate-result-filters-v1` / `610922781f1eec01e493122f8c1a3a50558e5bce`，开工干净，保留所有旧候选。共享1a8078／实体／主题均不改。
- 运行差异只有 CandidatePool `readingWidths` 的商品信息预算280–300→340–360及说明注释。沿原6:4分配剩余空间，宽度充足时店铺／类目分别让约36／24px，三列总宽不变；窄窗保留66／52最小值，允许必要横滚，不隐藏列或生成负宽。其它列宽及筛选／排序／分页／操作不变。
- 原居中、原生竖线、12px字体、48px图片、8px图文间距、8/12单元格padding、65px自然行、单行省略与全文Tooltip、字符串ID与固定复制槽全部沿用，不改共享API、后端、DB、Migration、平台、Electron或依赖。

## 同条件实际CSS测量（浏览器Mock，不是Electron）

旧测量：未改610运行源码，只加入测试测量；新测量：上述两处预算数值修改后。分别独立输出目录，旧截图不覆盖。数值为DOM实际宽度，含浏览器小数像素；不是模型估算或示意图。

| 视口 | 商品信息旧→新 | 店铺名旧→新 | 类目旧→新 | 三列合计旧→新 | 标题有效宽旧→新 |
| --- | --- | --- | --- | --- | --- |
| 1440×900 | 280→340 | 66→66 | 52→52 | 398→458（必要横滚） | 199→259 |
| 1920×1080 | 300.359→360.438 | 197.234→161.188 | 140.172→116.141 | 637.766→637.766 | 219.359→279.438 |

两次图片48、行高65、padding `8px 12px`、竖线1px和原ID均相同。1920下其它九列实际宽度逐项未变。

## 验证与证据

- `pnpm exec vitest run src/features/product-selection/ui/CandidatePool.spec.ts --maxWorkers=2`：8项通过（6.21s）。首轮误把无测量宽度时的合计预期改为1524导致1项失败；实际仍1494且保持原合计，已恢复原断言，不改运行逻辑凑测试。
- 受影响eslint、当前`pnpm typecheck`通过。未重复699、其它模块／全局竖线测试或真实平台请求；主题及实体代码逐字未变，复用610已有证据。
- 定向浏览器：`pnpm exec playwright test --config ../.codex/selection-product-info-mock.config.ts --grep 'candidate three-column width rebalance' --output ../.codex/candidate-width-rebalance-20261015/{previous,current} --reporter=line`。旧运行额外设 `PLAYWRIGHT_WIDTH_BASELINE=previous`，新运行不设；仅测试预期分支，不是产品能力开关。旧1项6.2s／新1项5.3s通过，覆盖普通／宽视口实际三列、标题、图片／行高／padding／边框及最小宽保护。
- 既有较长visual测试只同步新宽度断言及2240上限，不在本次重跑整个历史场景；此前未跑的旧`>360`宽屏断言已随本次明确上限修正，不隐瞒全套未执行。Real精确构建由ca97统一一次完成，Owner未重复。
- 截图与逐点JSON真实存在：`.codex/candidate-width-rebalance-20261015/{previous,current}/product-selection-candidat-32bea-ordinary-and-wide-viewports/{1440,1920}-{previous,current}-{candidate.png,widths.json}`。完整1920新图为该current目录的`1920-current-candidate.png`；旧目录保留，不复用输出路径。
- `git diff --check`通过；无共享／非Renderer差异，无DB或平台访问，不清任何数据／夹具／Profile，不另开Electron。

提交推送后精确Candidate交ca97增量检查并正常更新同一5180／Electron，保留账号、29条数据和0046；原生普通／最大化新效果尚待，不能把Mock视口叫作Electron验收。当前610已被用户要求返修，不继续催确认旧尺寸；新候选未确认不发布、不放行下游密度，不把独立真实basic Gate混入视觉。
