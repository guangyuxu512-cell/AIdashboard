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

AppShell 本身不需要 IPC，因此阶段 0B 不新增 Preload API 或 IPC Channel。
