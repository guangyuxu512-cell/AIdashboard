# 共用紧凑列表基础 V1 — Gate 1

## 范围与依赖

- Owner：81a1；分支 `feat/compact-product-list-foundation-v1`。
- 创建基线：精确 Green `9bb64ac76bf9e0f51fb1715517cf8c18cef63e22`。
- 正常 no-ff 同步资源登记 `5a27a562ae652a774325e99ec66f3fd942e550a2`；它不是新 Green。
- 原候选池分支 `feat/product-selection-candidate-result-filters-v1` / `bfaae14d76780f031e34ef68b139a26bb19b8694` 保留。共享分支不合入该分支或 7d55 业务。
- 本阶段仅共享尺寸能力及已审核的最小前置。之后正常 no-ff 合回原候选池分支，候选池显式试点另交精确 Candidate。用户原生确认前不扩展策略列表或商品数据页面。
- 不连接数据库、不启动 Backend、不修改 Schema/Migration/API/Electron/依赖。已有 Feature 0046 保持不动；本分支代码 Head 0045 不表示降级数据库。

## 已审核前置复用（普通同路径提交，不 cherry-pick）

逐文件来源：`bfaae14d76780f031e34ef68b139a26bb19b8694`，原始商品组件来源 `b364a89a9955ffe4aae1c3fb6dbfcabfd0dedf8f`，并保留 9734809 对已安装 Naive 2.45 Ellipsis 点击问题的 NTooltip 兼容、f876f83 的长标签修复。

| 路径 | 用途／默认边界 |
| --- | --- |
| `frontend/src/shared/ui/AppSelect.vue` / `.spec.ts` | 长标签 Tooltip 显式 opt-in；默认 false，自定义 renderer/tag/关闭回调不变 |
| `frontend/src/entities/shop/ui/ShopSelector.vue` / `.spec.ts` | clearable/labelTooltip 默认 false 的透传，不改变店铺查询与授权 |
| `frontend/src/entities/product/index.ts`、`ui/ProductImage.vue` | 公共商品图片；summary 80、thumbnail 64，contain/lazy/no-referrer/preview/retry 保留 |
| `frontend/src/entities/product/ui/ProductInfoCell.vue` / `.spec.ts` | 单行标题、原始字符串 ID／缺失保护／固定复制槽；Entity 不反向依赖 Feature |
| `frontend/src/features/product-selection/ui/ExternalProductImage.vue` / `.spec.ts` | ca97 明确批准的唯二 Feature 例外：既有图片薄兼容转发，去掉重复实现；不带任何业务代码 |

前置定向实际验证：`pnpm exec vitest run src/shared/ui/AppSelect.spec.ts src/entities/shop/ui/ShopSelector.spec.ts src/entities/product/ui/ProductInfoCell.spec.ts src/features/product-selection/ui/ExternalProductImage.spec.ts` — 4 文件、20 项通过（2026-10-15）。这不是紧凑模式或 Electron 验收。

## 显式 API 与共享变更白名单

- `ListDensity = 'default' | 'compact'`、`createListDensityTheme(density)`：`frontend/src/shared/ui/list-density.ts`，由 `shared/ui/index.ts` 导出。默认早返回 undefined，不读 DOM；compact 仅尺寸，不覆盖颜色、字体家族、圆角、locale。
- `density?` 默认 default：既有 `PageSection`、`FilterBar`、`ManagementListSection`、`TableToolbar`、`PaginationBar`。原根 DOM、attrs、fill、Slot、分页事件／页容量不变。
- `density?` 默认 default：`entities/product/ui/ProductInfoCell.vue`、`ProductImage.vue`。只有显式 thumbnail compact 为 48；summary80、默认thumbnail64 不变。ID 原始字符串复制／缺失禁用不变；compact ID12／复制槽28、缺图／失败槽48。
- 仅新增未被默认调用引用的六个 `--list-compact-*` 命名 Token；不改任何既有 Token 值或全局 Provider。
- 实际共享组件路径：`frontend/src/shared/components/{PageSection,FilterBar,ManagementListSection,TableToolbar,PaginationBar}.vue`；`PaginationBar.spec.ts`、`list-density.spec.ts`；上表前置路径；`entities/product/ui/ProductImage.spec.ts`；`shared/styles/tokens.css`；`shared/ui/{list-density.ts,index.ts}`。
- 仅测试浏览器入口：`frontend/e2e/fixtures/{list-density.html,list-density.ts,ListDensityHarness.vue}`、`e2e/compact-list-foundation.spec.ts`、`playwright.compact-list.config.ts`。不进入正式 Router 或生产构建；仅 4176 strictPort，无 Backend/API/seed/DB。
- 规范：`frontend/docs/03`、`09`、`10` 与本记录。治理父链新增记录由 5a27 正常合并而来，非本功能代码。

共享分支没有候选池页面／业务 DTO／API／Backend／数据库／调度／Worker／Electron／依赖改动。唯一 Feature 例外仍仅上述 ExternalProductImage 两路径。`bfaae14` 和 `b364a89` 均不是此共享候选祖先（`git merge-base --is-ancestor` 均返回 1），没有把业务整链带入共享。

## 实际验证（2026-10-15）

在 frontend 执行，Node 使用已有 bundled runtime；浏览器使用本机已有 Chromium headless shell。

| 命令／检查 | 结果 |
| --- | --- |
| `pnpm lint` | 通过 |
| `pnpm typecheck`，以及 `pnpm build` 内 typecheck | 通过 |
| `pnpm exec vitest run --maxWorkers=4 --reporter=dot` | 149 文件／699 项通过，116.08s |
| `pnpm build`（Real production） | 通过，15.69s；已有大包警告保留，无依赖变动 |
| `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=<已有本机shell> pnpm exec playwright test --config playwright.compact-list.config.ts --reporter=line` | 四主题 4 项通过，14.7s；外部／API请求 0，pageerror 0 |
| `git diff --check`、忽略检查 | 通过；AGENTS.override、test-results、dist 均忽略 |
| Real dist 搜索 `ListDensityHarness/list-density.html/product-1.webp` | 未匹配；测试入口／照片不进入 Real 包 |

四主题浏览器实际像素：表头／单元格／ID／输入／按钮 12px，筛选标签13px，输入／筛选按钮28px，卡片padding12，组合gap8，图片／缺图槽48×48，复制槽28×28，分页28px，图片行约65px（48+8+8+分隔）。无固定裁行。

- 紧凑 Select 菜单已 Teleport 至边界 DOM 外的 Overlay Host，选项12px／28px、长标签 Tooltip12px；原组件虚拟化保持，80项大列表只渲染可视项，滚动至第80项可选择／清除／键盘再选。
- 默认菜单14px／34px、默认 Tooltip14px；紧凑分页菜单12px／28px；切回 default 后输入14px／34px、卡片padding16，菜单恢复14px／34px。
- 默认消费者输入14／34、图片64；兄弟 Drawer 表单14／34、summary80、thumbnail64、ID13。此处是明确的 Vue sibling，不是仅换 Teleport target。
- 父主题对象 freeze／切换测试确认不可变，compact 合并后仍响应父颜色变化；不复制四套颜色。Token 单测改变为31px／29.5px时虚拟窗口读取对应值；空／0／负／无效值明确拒绝，无默认28或0兜底。
- 保留原字符串（含前导0和超长ID）、缺失禁用、成功／失败反馈；缺图／失败／重试48槽稳定。外部图片继续 no-referrer、无crossorigin和系统认证HTTP客户端。

首轮实际浏览器测试暴露 Naive 2.45 `depx(optionHeight)` 不支持 CSS var，造成空虚拟菜单，已从同一 Token 解析正像素值修复并补大列表回归。首次全量单测因旧 PaginationBar shallow provider stub 丢默认 Slot 失败1项，已只修该测试为真实抽象 Provider＋原分页 stub；最终全量699通过。浏览器断言另改为等待 Vue／弹层过渡稳定及当前 Tooltip，未放宽尺寸或关闭虚拟化。已有 AI jsdom XHR stderr 噪声仍有，测试通过；未借本任务扩修 AI。

截图（被忽略的实际浏览器夹具，不是 Electron／候选池验收）：`frontend/test-results/compact-list-foundation-*/{graphite,forest,coral,midnight}-scoped-foundation.png`。

## 交接、回滚及未覆盖

共享 Candidate 精确 SHA 随提交／推送后正式交接；随后原 bfaae Feature 正常 no-ff 消费，真实冲突逐路径记录，候选池 opt-in 另交 Candidate。**当前未激活任何业务消费者**，仅能力通过 Gate 1；ca97 独立 Gate 2 与新紧凑视觉原生确认未完成，不合 dev/main／不发布，不释放 7d55 依赖。

回滚为撤销本功能普通提交（共享历史用 revert），默认 API 可保留；无数据／Migration 回滚。原 Feature、0046、测试资料／Profile 均不删除。详情／策略／其它模块默认不变的浏览器／单测证据不代替 ca97 同一 Real Electron 的候选池试点，也不代替真实单商品 basic_info Gate。
