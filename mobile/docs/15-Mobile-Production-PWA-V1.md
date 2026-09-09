# Mobile Production PWA V1

## 状态与范围

本阶段将既有 Mobile 应用作为正式联网 Web App 接入生产 Frontend 镜像，并提供浏览器原生的添加至主屏幕能力。它不扩展任何 Mobile 业务页面，也不改变已冻结的 Visual V2、路由权限、Human Auth 或 Backend Contract。

正式入口：

- Mobile：`https://119.29.188.118/mobile/`
- Login 深链：`https://119.29.188.118/mobile/#/login`
- PC：继续使用根路径 `/`
- API：继续使用同源 `/api/v1/`

## Build 与 Route Contract

- Vite `production` build 的 `base` 固定为 `/mobile/`；Development 与 Visual Mock 仍使用 `/`。
- Vue Router 使用 `createWebHashHistory(import.meta.env.BASE_URL)`，确保生产导航始终停留在 `/mobile/#/...`。
- 既有 Frontend Docker image 同时构建 PC 与 Mobile；Mobile 输出复制到 Nginx 的 `/usr/share/nginx/html/mobile`，不新增容器、外部端口或反向代理层。
- `/mobile` 必须以 `308` 重定向到 `/mobile/`；`/mobile/` 与非静态子路径回退到 Mobile `index.html`。
- `/mobile/assets/`、`/mobile/icons/` 与 Manifest 的缺失文件必须返回 `404`，不能回退到 PC 或 Mobile HTML。
- PC 根路由与 `/api/` 代理保持原有行为，不得由 Mobile fallback 接管。

## PWA Contract

- Manifest 的稳定 `id`、`start_url` 与 `scope` 都限定为 `/mobile/`，`display` 为 `standalone`。
- 安装图标复用正式 `siyu-ai-mark` 品牌资源，提供 192、512、maskable 512 与 Apple Touch Icon。
- HTML 同时提供 Manifest、Apple Web App metadata 和 Light/Dark `theme-color`。
- 本阶段是联网 PWA，不注册 Service Worker，不实现离线业务、推送或私有响应缓存，也不控制 PC 页面。
- HTML 使用 `no-store/no-cache`，Manifest 与稳定文件名图标要求重新验证，带 hash 的 JS/CSS 使用 immutable cache；新版本重新打开或刷新后由最新 HTML 引用新 hash 资源。
- 不提供伪造的统一“安装”按钮。添加至主屏幕能力、入口位置和安装提示由实际浏览器与系统决定。

## Auth 与权限

- Mobile 继续复用既有 HttpOnly Human Session、`/auth/me`、Team Membership、`X-Team-ID` 与 Module Access。
- PWA 不保存 Session Token，不新增 JWT、认证存储或 Team Contract。
- `start_url` 只进入 `/mobile/`；既有 Route Guard 根据 Session 与当前 Team 决定进入登录页、首个有权模块或无权页。

## Release Archive 与健康检查

- Production archive 必须包含完整 `mobile/` build context，不得只包含 `mobile/package.json`。
- Frontend image build 同时执行 PC 与 Mobile production build。
- CI 在只读根文件系统的真实 Nginx image 中验证 PC 根入口、Mobile 重定向、Mobile HTML、Manifest、图标、hash JS/CSS 与静态缺失 `404`。
- 远端部署在既有 Frontend ready check 后读取 `/mobile/`，并验证 Manifest、安装图标和 HTML 引用的实际 JS/CSS；任一失败即沿用既有 release 回滚路径。
- exact SHA、SSH keepalive、并发组、Alembic、原子 release 切换与失败清理契约均保持不变。

## Gate 1 与发布后验收

Gate 1 必须运行 Mobile lint、typecheck、unit、production build、既有 Browser 回归和 `/mobile/` production-preview 回归；同时验证 360/375/390/430、Light/Dark、Console Error 与 Horizontal Overflow。

浏览器 production-preview 与容器回归只能证明构建、子路径和 Web App Contract。以下步骤必须在 Main 发布后用真实支持的手机浏览器单独记录：

1. 打开正式 HTTPS Mobile URL；
2. 使用系统/浏览器提供的添加至主屏幕入口；
3. 从主屏幕图标以独立窗口启动；
4. 登录，关闭应用，再次打开并确认 Session 恢复；
5. 发布后刷新或重新打开并确认加载最新版本。

没有上述真机证据时，只能记录为“代码与浏览器 Gate 通过，真机安装待验收”，不得写成安装已经通过。
