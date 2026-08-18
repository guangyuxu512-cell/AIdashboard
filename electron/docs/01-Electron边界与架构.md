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
