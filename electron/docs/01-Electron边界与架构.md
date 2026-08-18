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
