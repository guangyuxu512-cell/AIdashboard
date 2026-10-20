# 商品采集任务与商品库前端 V1 视觉返修 — Gate 1

日期：2026-10-20

Owner：81a1

下一责任人：ca97（独立 Gate 2 与唯一 Integration Electron 验收）

## 精确版本

- Green 基线：`65ecf3f72a6ae9ea3114d7404841ad9aae876565`
- Feature 分支：`feat/product-collection-library-frontend-v1`
- 原 Feature Candidate：`ab579f1dee3b289359242e6b1e7054c94ccf02dc`
- 共享下拉修复 Candidate：`ab2093bff2d7276f1ab82c30dc32eda1d9458bb8`
- 共享修复经 ca97 独立 Gate 2 后合入本分支：`153b1da`
- 本轮视觉返修实现：`e42fed6`
- 最终 Candidate：包含本记录的 Feature HEAD；完整 SHA 以正式 Handoff 为准。
- 交付仍为 `UI_ONLY`：Mock 交互与 Real 不回退边界不变。

## 本轮收口

1. 商品资料预览显式使用新的 `AppDialog size="xl"`，桌面目标宽度从原 `lg=720px` 提升为 `960px`；`md=560px`、`lg=720px` 和默认 `md` 均未改变，窄窗口仍受 viewport max-width 约束。
2. 商品库类目列从 `140px` 提升为 `360px`，完整类目路径最多两行并提供悬浮全文；表格基础 `scroll-x` 从 `1212` 同步调整为精确列宽和 `1432`，窄窗口保留横向滚动。
3. 采集任务的查询、批量重试和批量取消合并到同一条 compact `FilterBar`；窄宽度仅由该工具栏自然换行，不再额外占用第二条批量工具栏。
4. 商品库、采集任务列表继续显式使用 compact density；预览和详情位于密度边界之外，保持默认 14px／34px 控件尺寸。
5. 商品分组弹窗和新增成员弹窗的 `AppSelect` 默认菜单统一挂载到 `#app-overlay-host`，不再被 `.app-dialog` 的滚动／裁切边界截断；显式传入的挂载目标保持不变。

共享下拉根因是 Naive Modal 内默认 Select 菜单随组件局部注入，落入 `.app-dialog { overflow: hidden }` 裁切层。修复只调整共享 `AppSelect` 的默认菜单挂载契约，没有增加页面 z-index、`to-body` 特例或关闭弹窗裁切。

## Gate 1 验证

| 验证 | 结果 |
| --- | --- |
| `pnpm run lint` | PASS |
| `pnpm run typecheck` | PASS |
| `pnpm run build` | PASS：Real production，5830 modules；仅既有 chunk-size warning |
| `pnpm test` | PASS：173 文件／959 项 |
| `product-collection-library.spec.ts` | PASS：6/6，单 worker |
| 商品中心＋选品相邻 Mock E2E | 21 PASS／1 FAIL；失败为既有选品详情 12px 旧断言与当前 8px 基线不一致，本分支自原 Candidate 起未改对应源码或测试 |
| `git diff --check` | PASS |

完整 Vitest 保留既有 jsdom 图片 XHR `AggregateError` 和 Naive provider warning，进程 exit 0，959 项全部通过。相邻 E2E 的已知失败没有通过改断言或扩大本轮范围掩盖，需由 ca97 在 Gate 2 记录并交对应选品 Owner 处理。

## 浏览器 Mock 证据

本机忽略目录，不提交 Git：

- `frontend/test-results/product-collection-library-gate1-20261020/`
  - `product-library-1440.png`
  - `product-library-1920.png`
  - `product-preview-1440.png`
  - `collection-tasks-1440.png`
- `frontend/test-results/product-collection-library-b73ef--themes-and-narrow-viewport-mock/`
  - 四套主题 × 商品库／商品预览／采集任务，共 12 张，960×720。

这些是实际代码的浏览器 Mock 渲染，不冒充 Integration Electron、Real API 或平台验收。

## 边界与交接

- 无 Backend、数据库、Migration、Worker、Electron 壳、平台请求、依赖或权限变化。
- 未启动第二个 Electron；未执行 Hosted CI、dev/main 合并或生产发布。
- 没有 push。私有仓库的 push／CI 继续由用户安排，ca97 可从共享本机对象读取精确 Candidate。
- ca97 需在唯一 Integration Electron 核对 960px 预览、完整类目可读性、同栏批量操作，以及商品分组／新增成员下拉的可见、滚动和点击。
- Real 模式继续不加载 Mock Store、不回退演示数据、不显示伪成功。
- 回退使用正常 Git revert 撤销本轮 Feature 提交及共享修复合并，不清 Profile、数据库或既有业务数据。
