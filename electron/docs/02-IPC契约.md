# IPC 契约

统一命名示例：
```text
system:get-info
file:select-directory
worker:get-status
worker:start
worker:stop
worker:restart
```

最终以项目现有 Contract 为准。

每个 IPC 必须定义：
- request type
- response type
- error behavior

Preload 暴露类型化 API，例如：
```text
window.desktop.system.getInfo()
window.desktop.worker.getStatus()
```

禁止向 Renderer 暴露通用 `ipcRenderer.send`。
