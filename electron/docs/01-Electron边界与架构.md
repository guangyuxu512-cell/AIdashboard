# Electron 边界与架构

```text
frontend Renderer
↓
preload
↓
ipc
↓
main
↓
services
```

推荐：
```text
electron/
├── main/
├── preload/
├── ipc/
├── services/
└── types/
```

IPC 只负责传输。
业务系统逻辑不得堆在 handler。
本地系统逻辑进入 service。

## Renderer AppShell

阶段 0B 的 AppShell 位于 Frontend `shared/components/AppShell.vue`。Electron Main 只负责创建安全窗口并在开发环境加载 Vite、生产环境加载 `frontend/dist`；导航、页面布局、Design Token 和前端状态仍属于 Frontend。

Windows 桌面窗口使用 `titleBarStyle: hidden` 与原生 `titleBarOverlay`，由现有 54px AppShell Topbar 承载统一标题区域。窗口最小化、最大化/恢复和关闭仍由 Windows 原生 Window Controls Overlay 提供，不在 Renderer 自绘。

Renderer 仅通过 `window.desktop.appearance.setTitleBarTheme(light | dark)` 同步 Window Controls Overlay 的图标颜色。该 API 不提供窗口控制、通用 IPC 或任意参数能力；Light / Dark / System 的模式解析仍由 Frontend Theme Store 负责。

## 管理端登录窗口生命周期

管理端登录身份与 Session 仅由 Main 在单次 attempt 的内存中暂存。Adapter 识别真实店铺并完成 Session 采集后，Main 标记系统关闭意图并主动关闭独立平台窗口；`closed` 事件只有同时满足 `identified + systemCloseRequested + sessionCaptured` 才保留确认状态。用户提前关闭会清空身份和 Session，并返回可重试的未完成状态。

取消、完成、应用退出和 30 分钟超时都会清空 Buffer；Session payload、密码不得写入磁盘或日志。Management Login Profile 仅保存完成接入后的平台与 partition 映射，不保存 Cookie payload。

阶段 3C-3 的 Session 恢复仍由 Management Login Service 承担：存在 shop 映射时复用本机 persistent partition，不存在时只在当前电脑新建 Profile。Main 持有 Backend Refresh Lease、expected version 与捕获 Buffer，Renderer 只看非敏感进度。用户提前关闭、取消、30 分钟超时和应用退出会请求释放 Lease；异常退出由服务器 Lease 到期兜底。Management Login Profile 是当前管理电脑本地浏览器身份环境，ShopSession 是服务器权威程序认证状态，两者不得同步或混用。
