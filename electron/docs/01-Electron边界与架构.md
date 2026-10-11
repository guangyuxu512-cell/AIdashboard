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

阶段 0B 的 AppShell 位于 Frontend `shared/components/AppShell.vue`。Electron Main 只负责创建安全窗口；开发环境加载已登记本机 Vite，Windows 正式安装包固定加载与 API 同站的
`https://119.29.188.118/` Production PC Frontend。打包后的 `file://` 页面不是正式 HttpOnly Cookie
Origin，不得通过放宽 CORS 或关闭 `webSecurity` 绕过。导航、页面布局、Design Token 和前端状态仍
属于 Frontend。

正式主窗口只允许同 Origin 导航；Preload 只向固定 Production Origin 及已登记本机开发 Origin
暴露既有窄范围 Desktop API，Main 对 IPC sender 再做主 Frame 与 Origin 校验。平台登录窗口使用
独立 persistent partition 且不加载 Preload。

Windows 桌面窗口使用 `titleBarStyle: hidden` 与原生 `titleBarOverlay`，由现有 54px AppShell Topbar 承载统一标题区域。窗口最小化、最大化/恢复和关闭仍由 Windows 原生 Window Controls Overlay 提供，不在 Renderer 自绘。

用户已取消应用外壳圆角需求，主窗口使用系统默认外缘，不自定义窗口裁切或向 Renderer 通知专用窗口状态。Windows 主窗口保留 hasShadow=false 阴影修复，不改变 frame/thickFrame（保留边缘缩放）、原生控制和安全边界；平台登录窗口不变。正常窗口操作仍须实际 Electron 验证，不再设置自定义圆角验收门禁。

Renderer 仅通过 `window.desktop.appearance.setTitleBarTheme(light | dark)` 同步 Window Controls Overlay 的图标颜色。该 API 不提供窗口控制、通用 IPC 或任意参数能力；Light / Dark / System 的模式解析仍由 Frontend Theme Store 负责。

Windows 发行身份固定为 App ID `com.siyu.controlcenter`，userData 固定为
`%APPDATA%\Siyu AI Control Center`。版本升级只覆盖应用文件，不迁移或删除人员 Cookie、平台
partition 与本地 Profile mapping。

## 管理端登录窗口生命周期

管理端登录身份与 Session 仅由 Main 在单次 attempt 的内存中暂存。新店 Onboarding 保留既有行为：Adapter 完成身份识别与采集后主动关闭平台窗口，`closed` 同时满足 `identified + systemCloseRequested + sessionCaptured` 才保留确认状态。抖店在 Main 识别身份；拼多多采集固定身份接口适用 Cookie，再经 Backend 成功验证 `mallId / mallName` 才标记识别成功。Cookie 存在、页面加载或 URL 跳转均不构成成功。

已有店铺登录与列表/详情同一流程：复用本机 Profile，等待正常人工登录；已登录时自动捕获，后端用当前候选重新验证真实目标身份后才 CAS 保存。成功结束 attempt、清除 Buffer/计时器并原子释放租约，保留平台浏览窗直到用户关闭；再次点击先复核当前权限再只置前，不重新保存。提前关闭、取消、失败、错店不覆盖原 Session。主窗口关闭/应用退出立即关闭捕获及保留窗口，不能等待离线 Backend 才清理；释放失败沿用服务器租约到期兜底。

取消、完成、应用退出和 30 分钟超时都会清空 Buffer；Session payload、密码不得写入磁盘或日志。Management Login Profile 仅保存完成接入后的平台与 partition 映射，不保存 Cookie payload。

阶段 3C-3 的 Session 恢复仍由 Management Login Service 承担：存在 shop 映射时复用本机 persistent partition，不存在时只在当前电脑新建 Profile。Main 持有 Backend Refresh Lease、expected version 与捕获 Buffer，Renderer 只看非敏感进度。用户提前关闭、取消、30 分钟超时和应用退出会请求释放 Lease；异常退出由服务器 Lease 到期兜底。Management Login Profile 是当前管理电脑本地浏览器身份环境，ShopSession 是服务器权威程序认证状态，两者不得同步或混用。
