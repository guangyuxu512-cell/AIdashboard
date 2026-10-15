# 候选池紧凑列表试点 — Gate 1 / Handoff

## 精确依赖与范围

- Owner 81a1；原分支 `feat/product-selection-candidate-result-filters-v1`，保留已验 `bfaae14d76780f031e34ef68b139a26bb19b8694`。
- Green 创建基线仍 `9bb64ac76bf9e0f51fb1715517cf8c18cef63e22`。
- 纯共享 `6ac6638be37026edb20fb8023ab4a4b7661e53c2` 已独立封存 Gate 1，ca97 独立 7 文件 29 项及源码边界复核接受进入试点，不等于完整 Gate 2 或 7d55 依赖放行。
- 在原 Feature 正常 `--no-ff` 合共享，合并提交 `cb9841e692beb4086e9374db84ee869306339ae7`。未 reset/rebase/cherry-pick，原成果／0046／本机材料不删除。

### 真实合并冲突

仅三个 add/add：`frontend/src/entities/product/ui/{ProductImage.vue,ProductInfoCell.vue,ProductInfoCell.spec.ts}`。先核对 bfaae 三路径与共享前置 70052be 逐字一致，再保留 6ac 的显式 density 增量及全部已验标题／原始ID／缺失保护／Tooltip／图片预览重试；合并结果这三路径与 6ac 一致。其它 Selector／Facade／规范正常合并，无 backend 或 migration 冲突。

## 本次试点改动

运行代码仅 `frontend/src/features/product-selection/ui/CandidatePool.vue`：

- 既有 FilterBar、ManagementListSection、TableToolbar、PaginationBar 显式 `density="compact"`；商品信息 render 传 ProductInfoCell compact。
- 删除本页已由共享主题提供的重复 8/12px Table themeOverrides；现有列宽、字段、固定列、排序、过滤、分页、权限、查询与动作不改。
- CandidateDetailDrawer 仍在以上 Vue provide 边界**之外**；不是靠 Teleport 改 DOM 位置伪隔离。策略列表／策略抽屉／候选详情／店铺及经营页不启用 compact。
- 无 API／Backend／数据库／Migration／队列／平台／Worker／Electron／依赖变动；不申请 DB 或 Slot、不连接库、不发平台请求；0046 原文件保留。

本页列宽沿用 bfaae（CSS px）：选择44，商品信息至少260且承担剩余空间；商家至少66、类目至少52；rank54–88，首次上榜84，发现66–88，价格80–112，差评率84–96，上架日期106–140，状态82–100，操作220。左固定选择／商品信息，右固定操作；按实际容器计算，仅必要时 scroll-x，不在本轮另改列或压缩按钮。

## 实际验证

| 命令／范围 | 实际结果 |
| --- | --- |
| `pnpm exec vitest run src/features/product-selection/ui/CandidatePool.spec.ts src/shared/components/list-density.spec.ts src/entities/product/ui/ProductImage.spec.ts src/entities/product/ui/ProductInfoCell.spec.ts --maxWorkers=4` | 4 文件23项通过；包含新消费点／详情 sibling、原功能与固定列配置不变 |
| `pnpm exec eslint src/features/product-selection/ui/CandidatePool.vue src/features/product-selection/ui/CandidatePool.spec.ts e2e/product-selection.spec.ts` | 通过 |
| `pnpm typecheck`（本试点代码） | 通过 |
| `pnpm exec playwright test --config ../.codex/selection-product-info-mock.config.ts --grep 'candidate product identity fits\|centered candidate columns' --reporter=line` | 2 项通过，1.1m；实际 Mock 页面，不是组件夹具 |
| `git diff --check`／Git Ignore／范围 | 通过；截图、dist、AGENTS.override 和 .codex 忽略 |

两项既有浏览器检查仅更新受影响的列表 64→48px／约81→65px 和表头最小高度断言，未放宽间距、固定列、字段、操作或详情要求。实际四主题；1366×768、1440×900、1920×1080、2560×1390 全页与固定列／必要横滚；复制原字符串／缺ID、长标题省略与悬浮、勾选翻页清空、详情开关、上下 padding8／左右12、操作可见gap12通过。详情 summary80、四项指标22／正文14、两列边框及两个时间语义保持；原始区间、真实0／缺失不变。

复用**逐字未变**的共享 6ac 证据：完整前端149文件699项、全量lint、typecheck、Real build15.69s及四主题4项Portal／虚拟80项／默认消费者／父主题不变性。没有为试点重复跑699或无关模块。原 Real API／不混Mock的 bfaae 检查保留，消费点只改密度且 Mock/Real 共用同一组件；本轮未重新宣称任何真实平台／数据库／basic_info成功。精确试点 Real build 由 ca97 统一集成检查一次，Owner未重复构建；此未执行项明确保留，不把6ac构建误写成新SHA已构建。

## 实际截图与预览

浏览器 Mock 运行地址 `http://127.0.0.1:4176/#/product-selection`，仅上述自动测试期间使用，测试后停止；不是常驻新验收窗口。运行源为本候选的 CandidatePool＋6ac 精确共享代码，无后台 API 或真实平台请求。没有启动第二个 Electron，也未操作现有 Profile。

- `.codex/selection-product-info-mock/product-selection-candidat-23ff9-nd-accessible-fixed-actions/{1366,1440,1920,2560}-{theme}-mock-candidate-fit.png`。
- `.codex/selection-product-info-mock/product-selection-centered-d2611-red-themes-at-two-viewports/{theme}-{1440,1920}-candidate-plain.png` 及同目录详情截图／实际像素JSON。
- 这些是实际候选池／详情页面，与共享夹具截图分开；不是 Electron 证据。截图已给规划／ca97完整路径，未提交Git。

最终 Candidate 精确 SHA 在推送后正式消息提供。ca97 接收后按原入口更新**同一**5180和唯一 Real Electron、核实实际加载SHA，用户只补新紧凑尺寸确认。bfaae旧界面确认继续有效但不代替新密度确认；不重新问整体设计。

## 状态、风险与下一负责人

候选池试点代码及定向自检完成；新紧凑视觉原生确认／整体 Gate 2 尚未完成，尚未部署。7d55仍不能先消费共享／扩展商品页；选品策略列表待本试点确认后按同一规则推进。商品库／采集任务继续占位，不新造列表。真实单商品 basic_info 由 ca97 独立跟进，不能阻塞此视觉预览也不能被此视觉测试替代。

下一负责人 ca97：独立精确构建及同一 Electron 预览，不重复未改的完整测试；必要问题退81a1，不代修业务。Main/dev/生产本轮均未操作、未获自动发布。回滚为正常 revert 试点消费提交，保留共享默认 API 和0046，不回滚／清理数据或用户材料。
