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

当前 Preload 未引入打包器且保持 `sandbox: true`，因此运行时白名单在 Preload 单文件内声明，并与 `electron/types` 的正式 Channel 常量保持一致；不得通过本地运行时 `require` 破坏 Sandboxed Preload 加载。

## Management Login

```text
management-login:open
management-login:focus-shop
management-login:get-status
management-login:complete
management-login:refresh
management-login:close
```

`open` 只接受已注册的 `douyin` 或 `pdd` 平台、可选 UUID attempt ID和correlationId，以及白名单化的 Session 恢复上下文（shop、lease、expected version）；`get-status` 返回状态与 Cookie 数量等非敏感元数据，仅首次新增 Onboarding 可返回已识别的店铺身份；`complete` 完成首次接入；`refresh` 由 Main 将 Adapter 持有的新 payload 直接提交 Backend 并触发服务器立即验证；`close` 关闭尝试、清除 Main 内存 payload 并释放恢复租约。

已有店铺恢复的全部状态均返回 `identity=null`，包括首次 identified、失败、显式继续及 lease 已释放阶段。
此边界取决于 attempt 原始且不会随 lease 清空的 `recoveryShopId`，不能只判断可变的 `recovery`。
Main 内部身份及候选 payload 仍用于既有权威验证和保存；Renderer 仅使用当前授权 Shop 的目标信息，
不得在验证前从 IPC 取得候选他店名/ID。首次新增的身份确认展示及主动自动关闭保持原行为。

`complete` 与 `refresh` 的成功结果均含 `profileMappingWarning: string | null`。Backend 已成功而本机 `shop_id → partition` 映射无法保存时，Main 返回成功结果和该告警、清理尝试，不允许 Renderer 把它当作可重发的业务失败；下次恢复按无可用本机 Profile 处理。

`focus-shop` / `window.desktop.managementLogin.focusShop({platform, teamId, shopId, correlationId?}) → Promise<boolean>`
只接受已注册平台和店铺UUID；teamId可缺省，提供时必须UUID，null/空串/非法UUID均拒绝。
correlationId可选且必须UUID，其余多余字段仍拒绝。Main 用主窗口的现有人员 HttpOnly Session
先查询正式 ShopSession 元数据复核当前团队权限，再置前 shop_id 唯一的保留浏览窗；没有窗口返回 false。
共享店铺切团队后不新开第二窗；未完成 attempt 仍绑定原团队，不能借切团队复用原授权捕获。
这条路径不获取租约、不捕获、不保存，不把保留窗口当成保留权限。旧客户端没有该方法时 Renderer 提示安装新版，不能走假同步。

新Preload仅增加常量`managementLogin.correlationSupported: true`，不增加IPC通道或通用版本框架。
Renderer仅在此标记严格为true时传correlationId；已发布1.0.4没有标记，继续使用原白名单参数。
禁止遇参数拒绝后盲重试或放宽校验。新Main对无关联字段的旧调用自行生成随机记录ID；完整
Renderer/Main关联记录须匹配候选Renderer和桌面包，不能把版本不匹配产生的失败当原故障。
focus/open有界失败只回固定`SHOP_LOGIN_<CODE>`错误标记：超时、人员认证缺失、403及HTTP错误
分别表达；未知错误不反射message，也不提示平台Session已过期。已打开捕获窗的置前超时不取消捕获。

1.0.6新Preload增加固定`managementLogin.globalShopLoginSupported: true`。仅已有店铺恢复
（open携带合法recovery）允许teamId缺省/undefined；首次新增open无recovery仍必须提供团队UUID。
Main复用真实人员Cookie；无团队不发送x-team-id，不伪造/自动选择团队，不增成员关系。Backend
GET session、租约、刷新均由真实super guard校验；没有团队的普通成员或撤销人员仍拒绝，不以
Renderer旗标代替授权。已有团队调用和首次新增流程保持原契约。
Renderer只有明确支持标记时允许超级账号无团队调用；旧1.0.5保留原teamed调用，未选团队提示
升级桌面，而不是要求选团队或失败后盲重试。共享登录流仍对人员/团队/权限变化立即abort。

已有店铺 `refresh` 要求后端同 shop、VALID、expected version+1、非缓存验证及真实验证时间。
成功清除捕获 Buffer/计时器/恢复上下文/attempt，只保留窗口索引，平台窗口继续浏览；关闭后再登录可重新同步。
同店 open、状态检测及保存均 single-flight；取消或退出后的迟到结果不再提示成功。
新店 `complete` 的识别后自动关闭和 Onboarding 契约保留。

`get-status`返回类型仍为非空`ManagementLoginStatusResult`，不新增通道。支持失败留窗的新 Preload
增加固定可选标记 `managementLogin.refreshRecoverySupported: true`；状态可含
`refreshFailure: {code, canContinue}`。code 仅为 `candidate_rejected`、`identity_mismatch`、
`platform_auth_invalid`、`lease_expired`、`version_conflict`、`personnel_auth_required`、`forbidden`、
`validation_incomplete`，不反射 Backend 原始 message/body。仅 `candidate_identity` 或明确
`PLATFORM_IDENTITY_MISMATCH` 生成 identity_mismatch；403 优先保留权限分类。

失败状态的 `recovery=false` 表示旧租约已由 Main 接管释放，不表示窗口已经关闭。
Renderer 只有固定能力标记严格为 true 且有 refreshFailure 时才保留当前失败窗口并只读观察；
旧桥接仍走既有安全清理，不假装支持续跑。再次“登录”必须先取得新 lease/当前版本，经原 open
白名单重新关联同一目标 attempt；不能重放消费过的 lease、切换目标或自动提交。canContinue=false
时固定入口只经当前权限复核置前，另保留取消；同候选去重和三次 POST 上限不放宽。

真实窗口关闭时，即使已有检测/捕获Promise未返回，等待中的同一IPC也返回最终closed状态，
不能要求Renderer再发下一次poll才能获知关闭。已有终态先于共享pending检查；未知attempt仍拒绝，
不返回null或伪造关闭。Main主动Onboarding自动关闭保留identified与捕获元数据，不能误清确认页。
closed且recovery=false表示Main已接管该租约的释放尝试（并非确认远端DELETE成功）；Renderer
清理active/忙态和旧focus，不再重复释放。释放失败继续服务器过期兜底；旧桥接/查询失败保持原清理路径。
轮询停止后的晚到结果/错误不再调用回调，空响应报告安全读取失败而非登录失效或成功。

Cookie、Token、localStorage 与 sessionStorage 不返回 Renderer。平台规则实现于固定 `PlatformAuthAdapter`，Renderer 不能传任意 URL、JavaScript、Shell 或文件路径。拼多多 Adapter 只采集适用于 `mms.pinduoduo.com` 的 Cookie；首次新增时 Main 通过 Backend 预检成功取得店铺身份后才将非敏感 ID/名称放入现有 Status IPC，已有店铺恢复仍不返回捕获身份。恢复时优先读取本机 shop 到 partition 的映射；映射不存在才创建新的 `persist:management-login-<attempt_id>`。Profile 位于 Electron `userData` 且永不上传。
