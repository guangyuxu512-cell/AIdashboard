# 候选池短标题＋全局竖线 — 增量 Handoff

## 提交关系与最小改动

- 人类确认：规划 turn `01a13e0d-f1df-7cb1-977d-70262e09218c`。保留 `b99f4265a35744f854e03f1ffb0320e9c9dafe17` 与共享6ac；不把新设计授权记作原生验收或发布批准。
- 纯共享精确候选 `1a8078d0cd9917afc11454e84ff0d13d15a1a2f2`，正常追加在6ac，运行仅AppTable原生 `singleLine=false`。ca97已独立5文件23项／5份blob复核接受进入消费；默认密度／主题／Product实体不改。
- 原 `feat/product-selection-candidate-result-filters-v1` 正常no-ff消费，合并 `7e37c6b81f1c141e1d79e3abb0ffb2d7e4a646c9`，无冲突。没有reset/rebase/cherry-pick或整合7d55业务。
- 候选池运行增量仅 `CandidatePool.vue` 的局部 `readingWidths`：商品信息列280–300px，预算48px图＋8px间距＋约200–220px文字＋24px padding；实际列宽也收紧，不是只给span加max-width而留下大空洞。剩余空间交商家／类目，店铺列相对旧宽屏位置前移；其它字段／数字列／220px操作／左右固定列／筛选分页与业务不变。窄屏保留必要横滚，不隐藏列。
- 实际测量标题有效宽约199–219px（含原生1px边框），单行ellipsis／全文Tooltip，短文本不拉伸；相邻文字至少24px。图／缺图／标题和ID原起点、固定复制槽及完整字符串保护保留。
- 沿原居中：list表头／单元格／操作居中；商品信息内部原图＋标题／ID布局保持，不强行改有业务语义的grid对齐。详情原边框／字体／图片／时间字段不变。
- 不需要新增ProductInfoCell宽度API；共享实体与1a8078/6ac逐字相同，不给未来消费者新增无用参数。

## 实际验证（2026-10-15）

- 当前试点：`pnpm exec vitest run src/features/product-selection/ui/CandidatePool.spec.ts src/shared/ui/AppTable.spec.ts --maxWorkers=4`，2文件11项通过（6.38s）。列预算280–300、完整字段／copy/失效保护及新密度消费、原生grid/list／选中／sorter／fixed配置覆盖。
- 当前试点受影响eslint与`pnpm typecheck`通过；不重复未变699，不重跑后端／数据库／平台。精确完整候选Real build由ca97集中一次完成，Owner未重复构建，不能把父构建写成本候选已构建。
- `pnpm exec playwright test --config ../.codex/selection-product-info-mock.config.ts --grep 'candidate product identity fits' --reporter=line`，1项通过（36.1s）：4主题×1366×768／1440×900／1920×1080／2560×1390实际页面；标题预算／列宽／间隔断言、48×48图／约65px自然行、同起点复制槽、全文hover、原始长ID复制、缺失ID禁用、固定列／必要横滚、勾选换页／详情开关均通过。没有扩大业务或真实请求。
- 纯共享阶段另有23项与四主题4项代表页实测（13.6s），见独立全局竖线Gate1。源码搜索仅AppTable使用NDataTable；17个业务DataTable入口及经营直接AppTable覆盖，div卡片／树／空态／NDescriptions／未合7d55为明确例外，不冒称所有自定义列表都变为表格。
- 共享代表页测试检查表头／正文1px solid同语义色、默认字体14px／控件34px未泄漏，店铺选择／右固定操作及横滚。只有既有candidate显式紧凑，不推广策略／其它模块密度。
- `git diff --check`通过；Backend/Electron/Worker/依赖/0046相对b99零变化；未连DB、不改生产／配置、不发平台请求、不清Profile／夹具、不另开Electron。

## 截图精确路径与限制

当前实际候选池完整输出已复制至独立、不再复用的被忽略目录：

`C:/Users/Administrator/.codex/worktrees/81a1/中控台/.codex/candidate-title-dividers-v1-20261015/product-selection-candidat-23ff9-nd-accessible-fixed-actions/`

内有16张实际浏览器Mock全页图：`{1366,1440,1920,2560}-{graphite,forest,coral,midnight}-mock-candidate-fit.png`。例如`1920-graphite-mock-candidate-fit.png`、`1440-midnight-mock-candidate-fit.png`。尺寸测量为上述测试中的实际DOM断言；本次没有单独保存逐点原始像素JSON，不伪造该文件。

更正共享代表页截图可用性：1a8078阶段的PNG生成后，后续候选池测试复用了同一Playwright临时outputDir，测试器已自动回收上一组PNG；不是文件名拼写差异，现不能用其旧路径交付。对应四主题4项PASS／像素断言仍有执行记录，未为找图重跑已过测试。当前候选池16图已独立保存，未清理任何业务数据／源码／测试夹具／Profile。此限制已正式通知ca97，不能拿当前候选池图冒充已回收的代表页图。

## 下一步与门禁

完整Candidate精确SHA随推送正式交ca97；原唯一5180/Electron当前仍b99，在Root精确构建和检查后更新，保留8100／Profile／29候选／0046。新实际布局及全局竖线尚待一次集中原生确认；旧确认不重复、新确认不伪造。7d55等待新共享SHA及ca97放行，不先消费旧6ac；不合dev/main、不发布生产。

共享一行开关和候选池宽度改动可分别revert，无数据回滚；保留所有已应用迁移与历史。真实basic_info Gate继续单列，不让其阻塞本次视觉交付，也不以截图替代真实闭环。
