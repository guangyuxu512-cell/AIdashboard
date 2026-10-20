# 商品采集任务与商品库前端 V1 — Gate 1 交接

日期：2026-10-20

Owner：81a1

下一责任人：ca97（独立 Gate 2）

## 精确版本与边界

- Green 基线：`65ecf3f72a6ae9ea3114d7404841ad9aae876565`
- Feature 分支：`feat/product-collection-library-frontend-v1`
- 实现提交：`ed20dad91d265476f35175fb8aa22f47bd3bde40`
- 最终 Gate 1 Candidate：包含本记录的 Feature HEAD，完整 SHA 以正式 Handoff 为准。
- 参考 HTML：`capture-product-workspace.html`，SHA-256
  `0C8267563B9A7344587857302568C565DD493F90938D373A7C4EB24B0FA37E16`。
- 交付状态：`UI_ONLY`；显式 Mock 交互完成，Real 正式服务未接入。
- 无 Backend、数据库、Migration、Worker、Electron 壳、平台请求或新依赖变更。

## 已完成功能

### 采集任务

1. 在既有 `/product-selection?tab=collection-tasks` 内替换占位，不增加路由、菜单或权限码。
2. 平台展示复用 Platform Registry；拼多多继续使用正式代码 `pdd`。
3. Mock 支持抖店商品 ID／链接、已有店铺口令，创建时校验格式和重复项，失败保留草稿。
4. 支持任务计数／状态／平台／关键词筛选、分页、详情、失败重试、选中取消和已完成商品查看。
5. 列表只展示公开状态；接收回执、详细进度、入库状态和失败原因仅在详情展示，不把“已接收”写成“已入库”。
6. 候选池 Mock 批量采集和商品库 Mock 重新采集进入同一内存任务源。
7. 拼多多只声明手机端手动返回资料边界，淘宝只显示规划状态，未伪造自动采集。

### 商品库与资料预览

1. 复用既有 `/products` 路由及 `product-library` Guard，默认 20 条／页。
2. 列表支持关键词、平台、类目、业务分组筛选；保持字符串商品 ID、缺失值 `—` 和真实 0 的区分。
3. Mock 支持新建分组、批量移动、重新采集、删除，所有回馈均明确未写入正式商品库。
4. 导入入口支持 TXT、ZIP 和文件夹选择；只展示文件清单和目标分组，未解析或写入。
5. 单商品导出展示 TXT 清单，批量导出展示 ZIP 清单；Mock 不生成或下载真实文件。
6. 资料预览包含主图／详情图／SKU 图、基础信息、SKU、属性、图片清单、资料包和采集历史；图片等比、支持预览和失败重试。
7. 支持复制标题、基础信息、SKU 和全部信息；AI 改图／审图可见但禁用，未伪造 Provider 或成功结果。

## 复用清单

- `ContextSwitchBar`：选品库上层 framed 导航和任务平台／状态切换。
- `FilterBar` / `FilterField`：任务和商品库筛选区。
- `ManagementListSection` / `TableToolbar` / `DataTable` / `PaginationBar`：紧凑列表、批量操作与分页。
- `AppDialog` / `AppButton` / `AppInput` / `AppSelect` / `AppRadio`：弹层和基础表单控件。
- `ProductImage` / `NImage`：商品缩略图、详情等比预览和失败边界。
- `PlatformDisplay` / `PlatformIcon` / Platform Registry：平台名称、图标和代码。

## Gate 1 验证结果

| 验证 | 结果 |
| --- | --- |
| `pnpm lint` | PASS |
| `pnpm typecheck` | PASS |
| `pnpm test` | PASS：173 文件／953 项 |
| 定向 Playwright Mock | PASS：7 项，单 worker |
| `pnpm build` | PASS：Real production，5830 modules；仅既有 chunk-size warning |
| Real 夹具白名单扫描 | PASS：6 个独特 Mock 商品／任务值均 0 匹配 |
| `git diff --check` | PASS |

Vitest 保留既有 jsdom 图片 XHR `AggregateError` 和 Naive injection warning，进程 exit 0，953 项均通过；本轮没有通过改断言隐去 warning。

## 浏览器证据（本机忽略，不提交）

路径：
`C:/Users/Administrator/.codex/worktrees/81a1/中控台/docs/_local/product-collection-library-frontend-v1/`

- 四套主题各包含：采集任务、商品库、商品预览。
- 共 12 张实际代码渲染截图，视口 960×720，图片加载完成后截取。
- 该证据为浏览器 Mock，不冒充 Electron、Real API 或真实平台验收。

## Real 边界

- Service Factory 只在构建与运行均为 Mock 时动态加载内存 Store。
- Real 返回显式 unavailable，不请求猜测 URL，不加载 Mock 商品／任务夹具，不显示伪成功。
- Real 产物仍包含共用页面的演示边界文案，但无 Mock Store 夹具；实际运行在 service unavailable 分支停止。
- 未接入：手机任务派发与回执、正式采集任务查询／重试／取消、正式商品库、分组持久化、导入解析、TXT／ZIP 生成下载、AI 改图／审图、百应及淘宝采集。

## ca97 Gate 2 建议检查

1. 以正式 Handoff 的精确 Candidate 加载唯一 Integration Electron，不启动第二窗口。
2. 核对选品库 framed 导航，以及采集任务、商品库、预览的四主题与窄窗口表现。
3. 核对创建校验／去重、候选池联动、任务详情，以及商品库 20 条默认分页、筛选、分组、导入入口和资料预览。
4. 以 Real 模式核对“正式服务未接入”，确认无 Mock 商品、无伪操作成功、无外部采集请求。
5. 技术或业务问题退回 81a1；通过后由 ca97 正常 `--no-ff` 合入 dev 并核对精确 CI。

## 未验证和发布状态

- 未执行 Integration Electron、Hosted CI、dev/main 合并或生产发布。
- 未调用真实平台、Backend、Worker 或数据库；没有 Migration Slot。
- 本 Gate 1 只证明前端／Mock 实现和 Real 边界通过，不宣称采集或商品库真实业务完成。
- 回退使用正常 Git revert 移除本 Feature，不清 Profile、数据库、既有选品或商品数据。
