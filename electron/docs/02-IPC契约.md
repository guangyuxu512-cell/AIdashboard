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

所有 Desktop IPC 仅接受主窗口主 Frame 且 URL Origin 与该窗口启动时固定的受信任 Renderer Origin
一致的 sender。Preload 的 Origin 白名单只是第一层；Main sender 校验不得省略。跨 Origin 页面、
子 Frame 和平台登录 BrowserWindow 均不能调用 Desktop IPC。

## Appearance

```text
Channel: appearance:set-title-bar-theme
Renderer API: window.desktop.appearance.setTitleBarTheme(theme)
Request: "light" | "dark"
Response: void
Error behavior: Preload 与 Main 均拒绝非法主题值；窗口已销毁或来源窗口不存在时不执行。
```

该通道只更新发起 Renderer 所属 BrowserWindow 的原生 Window Controls Overlay 图标颜色。它不提供最小化、最大化、关闭或任意 BrowserWindow 调用能力。

```text
Channel: appearance:window-state
Direction: Main → trusted Preload (notification only)
Payload: DesktopWindowState = "normal" | "maximized" | "fullscreen"
Effect: validated value → document.documentElement.dataset.windowState
```

Main 在加载完成及窗口 resize/maximize/unmaximize/fullscreen/restore 时同步状态。Preload 仅在既有白名单 Origin 安装监听，只接受三种值；不暴露 IPC 或窗口操作 API。Renderer 外壳用此状态决定页面圆角，业务数据不参与。刷新后重新同步，不持久化瞬时窗口状态。

当前 Preload 未引入打包器且保持 `sandbox: true`，因此运行时白名单在 Preload 单文件内声明，并与 `electron/types` 的正式 Channel 常量保持一致；不得通过本地运行时 `require` 破坏 Sandboxed Preload 加载。

## Management Login

```text
management-login:open
management-login:get-status
management-login:complete
management-login:refresh
management-login:close
```

`open` 只接受已注册的 `douyin` 或 `pdd` 平台、可选 UUID attempt ID，以及白名单化的 Session 恢复上下文（shop、lease、expected version）；`get-status` 只返回状态、可用时的真实店铺身份与 Cookie 数量等非敏感元数据；`complete` 完成首次接入；`refresh` 由 Main 将 Adapter 持有的新 payload 直接提交 Backend 并触发服务器立即验证；`close` 关闭尝试、清除 Main 内存 payload 并释放恢复租约。

`complete` 与 `refresh` 的成功结果均含 `profileMappingWarning: string | null`。Backend 已成功而本机 `shop_id → partition` 映射无法保存时，Main 返回成功结果和该告警、清理尝试，不允许 Renderer 把它当作可重发的业务失败；下次恢复按无可用本机 Profile 处理。

Cookie、Token、localStorage 与 sessionStorage 不返回 Renderer。平台规则实现于固定 `PlatformAuthAdapter`，Renderer 不能传任意 URL、JavaScript、Shell 或文件路径。拼多多 Adapter 只采集适用于 `mms.pinduoduo.com` 的 Cookie；Main 通过 Backend 预检成功取得店铺身份后才将非敏感 ID/名称放入现有 Status IPC。恢复时优先读取本机 shop 到 partition 的映射；映射不存在才创建新的 `persist:management-login-<attempt_id>`。Profile 位于 Electron `userData` 且永不上传。
