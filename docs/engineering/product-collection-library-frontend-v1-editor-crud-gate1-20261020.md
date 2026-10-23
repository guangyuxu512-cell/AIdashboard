# 商品库前端编辑与 Mock CRUD 收口 — Gate 1

日期：2026-10-20

Owner：81a1

下一责任人：ca97（独立 Gate 2 与唯一 Integration Electron 视觉／交互验收）

## 精确版本

- Green 基线：`65ecf3f72a6ae9ea3114d7404841ad9aae876565`
- Feature 分支：`feat/product-collection-library-frontend-v1`
- 上一轮视觉 Candidate：`d9824cfff77a2744bed29fc3f0ab94bbdafbc570`
- 本轮实现提交：`db31c4d191e1dd2c2f37bf261cc44bbb8032531c`
- 首次编辑器收口快照：`77aa56092bfd8cf4c915ce0e79034b18913cd686`（已被近全视口返修取代，不进入 Gate 2）
- 近全视口返修提交：`75a1cf5c86cc876aae80c5df740301566d67e713`
- 最终 Candidate：包含本记录的 Feature HEAD；完整 SHA 以正式 Handoff 为准。
- 交付状态：`UI_ONLY`。只完成前端与 Mock 交互，不表示商品业务、平台采集或 Real API 已接通。

## 本轮完成

1. 商品库固定为“全部商品／采集导入／分组商品”三种视图；分组仅作为分组视图的可搜索筛选条件，不再动态生成页签。
2. Mock 分组统一为“福利品／测试款／本周上架”，保留未分组商品；导入和移动分组沿用现有弹窗与可搜索 `AppSelect`。
3. 商品列表支持进入编辑、单项删除和原有批量删除；Real service 明确返回未接入，不回退 Mock 或伪造成功。
4. 在共享 `AppDialog` 增加 opt-in 的 `workspace` 模式，仅商品密集编辑器使用；它在 AppShell Topbar 以下工作区保留 8px 外边距并跟随窗口宽高，既有 `sm/md/lg/xl` 尺寸及其他页面默认行为不变。
5. 编辑器同时展示主图、SKU 图、详情图；支持标题、商品属性、规格维度、SKU 名称／规格值／价格及图片绑定的 Mock 编辑。
6. SKU 使用稳定 `draftKey` 与可空 `sourceSkuId`。前端新增 SKU 明确为无平台源 ID，不伪造平台身份；删除、新增、编辑和保存均保持显式图片绑定。
7. 保存与取消相互独立，未保存修改离开时触发脏数据保护；保存后 Mock 列表和再次打开的详情一致。
8. 右侧商品导航改为 320–360px 的贯穿同高列，显示 48px 缩略图、最多两行标题、平台及分组，只展示当前页或当前选择范围并支持直接跳转、上一件／下一件。
9. 外层 Body 不滚动，左侧编辑区与右侧列表各自使用一个内部纵向滚动区；固定 Footer 承载保存／取消／关闭。在 1920×1080、1366×768 和 1024×640 深滚动到 SKU 底部后，右侧导航和操作仍可达，SKU 表格的必要横向滚动不会裁掉价格输入。

## Gate 1 验证

| 验证                                                                                                                                                                                | 结果                                                                           |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `pnpm lint`                                                                                                                                                                         | PASS                                                                           |
| `pnpm typecheck`                                                                                                                                                                    | PASS                                                                           |
| `pnpm exec vitest run src/shared/ui/AppDialog.spec.ts src/features/product-library/api/product-library-mock-store.spec.ts src/features/product-library/model/real-boundary.spec.ts` | PASS：3 文件／9 项                                                             |
| `pnpm exec playwright test --config .dev-runtime/product-library-reuse.config.ts`                                                                                                   | PASS：10/10，单 worker，复用 4178 Mock 服务                                    |
| 隔离 Mock 构建                                                                                                                                                                      | PASS：5845 modules；输出 `.dev-runtime/product-library-frontend-v1/build-mock` |
| 隔离 Real 构建                                                                                                                                                                      | PASS：5830 modules；输出 `.dev-runtime/product-library-frontend-v1/build-real` |
| `git diff --check`                                                                                                                                                                  | PASS                                                                           |

两次构建仅保留仓库既有 chunk-size warning。最终构建显式使用忽略目录的 `--outDir`，没有再写默认 `frontend/dist`：构建前后该目录 `index.html` 的 SHA256 均为 `2A3BB8E03F4B1B1F0B911C409C493EAC4BFB77A63F4FF4A1BB8ACAD7CAF1B3D7`。隔离 Mock／Real `index.html` SHA256 分别为 `DB9B32FBE6746F9539669C0C2623E90F68BDC8A21D85AE187FA9EDA2BBFF733F`、`942F8DE8A432E563A40BE319829E6D4470BC2D8994979AE71B0559B9AB76DE16`。

## 浏览器 Mock 证据

当前 Owner 预览：`http://127.0.0.1:4178/#/products`。截图保存在本机忽略目录，不提交 Git：

- `frontend/test-results/product-library-gate1/product-collection-library-63dd7-iews-and-editable-SKU-state/`
  - `01-商品库三视图与分组筛选.png`
  - `02-近全视口商品编辑与整列导航.png`
  - `03-SKU新增删除与规格价格.png`
- `frontend/test-results/product-library-gate1/product-collection-library-b73ef--themes-and-narrow-viewport/`
  - 四套主题 × 商品库／商品编辑／相邻采集任务，共 12 张。
- `frontend/test-results/product-library-gate1/product-collection-library-eb0c9-after-deep-editor-scrolling/`
  - 1920×1080、1366×768、1024×640 的顶部与深滚截图，共 6 张。

这些是当前代码的浏览器 Mock 渲染，只用于 Gate 1，不冒充 Integration Electron、Real API、数据库或平台验收。

## 边界、风险与交接

- 无 Backend、数据库、Migration、Worker、Electron 壳、平台请求、Session、依赖或权限变化。
- 商品新增、真实导入／导出、真实图片替换、AI 改图、平台库存写回及正式商品 API 仍未接入。
- ca97 的 5180 冻结预览已恢复到上一轮 `d9824cfff77a2744bed29fc3f0ab94bbdafbc570`，本轮没有触碰；Gate 2 必须先加载最终 Candidate，再核对近全视口编辑器、左右独立滚动、贯穿同高导航、三图片区、SKU CRUD、脏数据保护和 Real 不回退。
- 没有 push、Hosted CI、dev/main 合并或生产发布；私有仓库后续动作继续由用户／ca97 安排。
- 回退使用正常 Git revert 撤销本轮 Feature／返修提交；无需清理数据库、Profile 或业务数据。
