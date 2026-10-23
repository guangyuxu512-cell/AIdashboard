# Shared Overlay Select Contract V1 — Gate 1（2026-10-20）

## 基线与范围

- Owner：81a1；分支 `fix/shared-overlay-select-contract-v1`。
- 精确 Green 基线：`65ecf3f72a6ae9ea3114d7404841ad9aae876565`。
- 实现提交：`05c2c747d7a3d997b993d8cdfb5d91193f65caf3`。
- 仅修改共享 `AppSelect` 的菜单挂载契约、定向浏览器测试及对应前端规范；没有 Backend、数据库、Migration、依赖、Electron 主进程或业务页面实现变化。

## 根因与修复

Naive UI 2.45 在 `to` 未指定且 Select 位于 Modal／Drawer／Popover 时，会采用最近的 Overlay Body 作为菜单容器。项目的 Dialog Body 需要独立滚动和裁切，因此菜单越过卡片边界时会被截断；提高 z-index 不能跨越该裁切边界。

`AppSelect` 现在遵循以下共享规则：

1. AppShell 已渲染 `AppOverlayHost` 时，默认将菜单和标签 Tooltip 挂到该 Host。
2. 登录页、独立夹具等没有 Host 的布局回退到 Naive 全屏层，不引用不存在的 selector。
3. 调用方显式传入 selector、HTMLElement、`true` 或 `false` 时原样保留，不改变隔离测试与特殊调用语义。
4. 不移除 `AppOverlayHost` 的 `overflow: hidden`／Fixed Containing Block，不修改 Dialog Body 裁切，也没有页面级 z-index、`overflow: visible` 或 `to="body"` 补丁。

## 验证

- `pnpm run lint`（`frontend`）PASS。
- `pnpm run typecheck`（`frontend`）PASS。
- `pnpm run build`（Real production build）PASS；仅保留既有 chunk-size warning。
- `pnpm test -- --run`：170 files／952 tests PASS；既有 jsdom XHR stderr 与 DataTable provider warning 保留，测试无失败。
- `AppSelect.spec.ts`：13 tests PASS，覆盖 Host／无 Host 回退及 selector、HTMLElement、true、false 显式目标。
- Mock Playwright：`auth.spec.ts`、`product-data.spec.ts`、`product-data-compact.spec.ts`、`schedules.spec.ts` 共 27 tests PASS：
  - 登录 Team Select 在无 Host 布局可键盘选择；
  - 商品分组 Dialog 的菜单位于 Host、脱离 Dialog，真实命中与键盘选择通过；
  - 620px 低视口内时区菜单可命中，并在 Dialog Body 滚动时跟随锚点；
  - 石墨浅色、森林绿、珊瑚红、午夜青四主题的菜单尺寸与挂载位置通过。
- `git diff --check` PASS。

首次从仓库根目录误调用 frontend 专属 `lint/typecheck/build`，因根 package 不定义这些脚本立即退出；随后在 `frontend` 目录按项目正式命令全部通过。首次新增键盘断言对默认高亮项预期不准，仅调整测试预期，最终 27 项整批干净通过；生产实现未为测试让步。

## 交接边界

ca97 对本 Shared Candidate 独立 Gate 2 后，商品资料 Feature 才以 no-ff 方式消费。当前未 push、未触发 CI、未合 dev/main、未部署，也未启动第二个 Electron；浏览器 Mock 证据不冒充原生验收。
