# AI 工作台 Real API V1

## 1. Production Data Flow

AI 生图、素材库、模板库与生成记录的生产路由直接使用 `/api/v1/ai-workbench`，文件统一使用其受限 `/assets` 子入口。TanStack Vue Query 负责 Catalog、列表、详情缓存与短轮询，页面状态只组合 Backend DTO，不在 Frontend 模拟生成成功。

```text
Model / Template / Material Catalog
→ explicit model_id Submit
→ GenerationJob 202
→ Job Detail Polling
→ GenerationItem + Asset
→ Result / Record / Retry
```

模型下拉框只展示支持当前 Mode 的启用模型，优先选择 `is_default=true`，并使用 `max_input_images / supported_sizes` 约束输入与尺寸。Backend 始终是最终校验边界。

## 1.1 Input, Preview And Output Policy

- ProductMaterialGroup 的素材角色在 Real API 映射中保持原值：`PRODUCT_SOURCE` 与 `STYLE_REFERENCE` 才能组成生成输入，
  `AI_OUTPUT` 只作为结果展示事实，不能自动成为下一次生成输入。页面分别展示商品原图、AI 成品与全部素材数量，
  不用文件名推断角色，也不静默截断超限输入。
- 模型能力缓存由模型管理与工作台共用。模型能力未知时不把输入上限误判为 `0`；模型限制更新后，两处查询同时失效并
  重新读取。提交前提示必须显示实际输入数量和模型上限，Backend 仍按每个 Item 完成最终校验。
- 图片缩略图、素材详情、生成结果和生成记录统一使用受保护 Asset Content/Thumbnail 链路。素材详情先显示已鉴权缩略图，
  再以 30 秒有界请求读取原图；原图成功后才替换缩略图，失败时清空缩略图并明确提供重试。共享预览支持完整比例查看、
  切换、下载、加载失败和重试；对象 URL 只在组件生命周期内存在，快速切换不能让旧请求覆盖新素材。
- 即时与批量页面共用“生成后压缩至 1000 KB 以下”输出设置，默认关闭并按当前身份与 Team 保存用户选择。Submit 时把
  该布尔值冻结到 GenerationJob；任务恢复、轮询和重试只展示或执行已有 Job 策略，不会因后来切换开关改变任务结果。

## 2. Management Pages

- 模板库使用正式 TemplateGroup 与 PromptTemplate 列表、详情、新增、编辑、删除、复制、排序和启停 API。
- 素材库使用正式 ProductMaterialGroup、Asset 上传/读取、Attach/Detach、Role 与 Template Binding API。
- 受保护图片通过共享 Human Request Context 获取 Blob，再创建页面生命周期内的 Object URL；Provider URL 不进入页面状态。
- 生成记录以 GenerationJob 为唯一事实来源，支持 Work Mode、Mode、Status 与分页。Real API 没有搜索 Contract，因此生产页面不展示 Mock 搜索框。

### 2.1 超级账号与团队上下文

- 全部团队可浏览素材、模板与生成记录，统一显示选团队提示；上传、新建、编辑、启停、删除、生成与失败重试不可用，预览和下载保留。生图页不在全局上下文挂载生成面板。
- 切换默认团队或其他具体团队后，读取与上传关联使用同一 `X-Team-ID`，由后端统一 Team 谓词过滤；默认团队不再混入别的团队素材。用户菜单可随时切回全部团队，超级账号身份不变。
- 切换团队时复用统一 Query/草稿清理，并关闭素材弹窗、删除确认与选择态。上传回执若迟于切换，不向新 Team 的素材组关联，也不在新 Team 发起清理；保留原 Team 文件并明确提示，不自动重传。
- `playwright.ai-images.config.ts` 在既有 Real 产物离线测试中覆盖上述菜单、全局只读、团队上传与迟到回执。受控 API 浏览器测试与独立 PostgreSQL 授权测试分开记录，不替代 Integration 原生验收。

## 3. Polling And Terminal States

Job Detail 在 `PENDING / RUNNING` 时短轮询；`SUCCESS / PARTIAL_FAILED / FAILED` 立即停止。记录列表仅在当前页存在非终态 Job 时轮询。失败重试调用 Backend 正式 API，Frontend 不自行改写 Item 状态。

工作台停留原页面或重新获得浏览器焦点时，非终态 Job 必须继续从 Detail Query 获取权威状态；
`PENDING → RUNNING → SUCCESS` 后直接使用返回的 `items[].output_asset` 展示图片。Detail 读取失败时显示
正式 Error State 与重新加载入口，不得继续用最后一份 `RUNNING` 缓存伪装成仍在生成。正常失败与
`PARTIAL_FAILED` 继续按 Backend Item 状态展示，Frontend 不伪造终态。

## 4. Navigation State Retention

同一浏览器、同一登录账号与同一 Team 内，AI 生图生产页使用 Pinia 与浏览器持久化保留客户端状态：

- 即时生成与批量生成分别保留草稿、输入 Asset ID、当前 `generation_job_id` 和必要的提交中状态；工作方式也随当前 Actor Context 保存。
- 路由切换由同一个 Store 承接；刷新或重新打开时必须先完成 Auth 与 Active Team 恢复，再按 `user_id + team_id` 加载对应状态。
- 已知 `generation_job_id` 的恢复只重新读取 Job Detail，不再次提交。若刷新发生在 Submit 回执返回前，只能复用持久化的原请求与原 `submission_key`，依赖 Backend 正式幂等契约取回同一 Job。
- Job 详情、结果与轮询仍由 TanStack Vue Query 和正式 API 管理，不复制到 Pinia。
- 草稿图片只持久化 Asset ID 与必要展示摘要；正式内容地址在恢复时重建，鉴权读取后创建的 Blob URL 按图片组件生命周期释放。Cookie、Token、图片二进制与 Provider 数据不得进入浏览器持久化。
- 退出登录、会话失效或切换 Team 时同步删除原身份状态；普通刷新初始化不得触发退出清理，清理前发出的异步响应不得回写新身份。
- “清空当前任务”只清除当前工作方式的草稿、任务引用、结果展示与本地持久记录。它不取消后台任务，也不删除生成记录、Asset 或 Storage 文件；即时与批量互不清理。

本能力覆盖当前浏览器内的路由往返、刷新与页面重新打开，不提供跨浏览器或跨身份共享，也不建设数据库草稿系统或全站 KeepAlive。

## 5. Batch Recovery Acceptance

- 批量页面以同一 `generation_job_id` 恢复运行中任务，继续通过 Job Detail Query 轮询；终态返回后按 Item 中的产品、模板组、模板快照与 `output_asset` 原地渲染分组结果。
- `SUCCESS / PARTIAL_FAILED` 刷新或重新打开后仍以后端 Job 为事实来源。已知 Job ID 只发起读取；Submit 回执中断只能以持久化的原请求和原 `submission_key` 恢复。
- 清空批量任务后，旧 Query 或迟到响应不得回写；即时草稿、生成记录和 Asset 不受影响。Job Detail 读取失败必须显示可重试 Error State，不得保留旧 `RUNNING` 结果持续转圈。
- 成功结果、生成记录和素材库下载复用统一 Asset Download Queue：只请求正式 Asset Content 原图地址，单次队列最多 3 个并发请求，提供进度、取消、逐文件失败重试及受控错误码/请求编号提示。下载专用超时为 120 秒，不改变页面预览的短请求策略；V1 没有 ZIP 或按产品/模板组文件夹打包 API，也不声称已支持按组文件夹下载。
- 生成记录详情的下载事件必须携带明确结果集合：单张只传该结果，下载组只传该组结果，下载批次才传整批结果；父级只将事件携带的成功结果转换为同一 Asset Content 下载队列请求，不得按记录重新扩展单张选择。
- 素材库仅承载用户上传或主动关联的产品参考图。生成结果已由 GenerationJob、GenerationItem 与输出 Asset 持久化，页面保留预览、下载、历史和恢复，但不显示素材库归属状态、不提供保存入口，也不调用生成结果归档 API。既有历史关联不在本阶段删除或迁移；旧归档接口的数据库失败仍待 Backend 单独调查。
- 自动化验收使用正式 Real 页面、真实 Query 链路与受控 API 响应，不接入 Visual Mock 执行状态。生产付费批量任务的完整闭环仍需在发布后使用一次正常任务验收。

## 6. Visual Mock Boundary

Visual Mock 仅在 Development 且查询参数精确为 `visualMock=1` 时动态加载，用于冻结视觉与交互测试。Production Build 默认且唯一运行 Real API 页面，不提供 Fixture fallback。

页面继续复用 AI Module Shell、Shared 状态组件、表单控件、分页和工作台结构。平台展示统一复用 `PlatformDisplay` 的固定图标槽与左对齐名称，不在业务页面分别补 margin。

## 7. Asset Image Display Contract

- AI输入、生成结果、素材库卡片/详情/选择器和生成记录统一由 `AssetContentImage` 内部真实图片执行 `object-fit: contain`。方形或4:3槽只是排版边界，不改变图片比例；横、竖、长图完整显示，留白正常，不裁切、不拉伸。
- 调用方必须提供固定尺寸、可解析高度或 `aspect-ratio` 槽。真实图片绝对定位在组件已有的有界 `relative` 容器中，避免图片固有尺寸撑大 Grid 轨道；占位只在无可显示图片时出现，不能与已就绪图片组成第二条轨道。
- 调用方不重复覆盖内部 `img` 的 fit，也不依靠普通 scoped `img` 选择器穿透子组件。非AI的 `ProductImage` 独立契约不变。
- 大图默认完整等比显示，现有缩放以左上角为锚点，让原滚动容器可达四边；切换图片恢复1倍，鉴权原图、缩略回退、错误重试、下载和 Blob 释放继续复用原链路。
- 自动回归先构建正式 Real Production Bundle，再执行 `pnpm --filter @control-center/frontend exec playwright test --config playwright.ai-images.config.ts`。测试无监听端口/Backend/数据库；HTTPS虚拟站点全部请求由路由拦截，沿正式页面与 Query 使用受控 API/SVG。四比例自然尺寸、computed fit、实际截图四色像素、放大边界及慢图/重试共同守门，不代表真实平台或原生Electron验收。

## 8. AI 文件上传与权限（2026-10-19）

- AI 上传、素材缩略/大图、下载、草稿恢复、生成输出与历史一律使用
  `/api/v1/ai-workbench/assets`，不得退回需要独立 `asset` 授权的通用资料库入口。共享 Blob/下载队列
  只消费完整 URL，不自行放宽授权；Backend 的 AI 文件资格为权威，见 Backend Real API 契约第5节。
- 只授予 `ai-workbench` 即可使用合法 AI 文件，不因此获得资料库枚举或任意删除权限。当前 Team 本人
  历史 UPLOAD 图片可作为草稿是明确例外，不声称上传来源隔离；切换 Team/模块撤销继续 fail closed。
- 图片大小预检只复用实体层单一 `assetMaxUploadBytes = 10 * 1024 * 1024`，Backend 永远最终校验。
  仅上传请求使用120秒有界超时，通用请求10秒、预览30秒及现有下载120秒不变；不自动重传。
- 多文件即时上传逐项结算：一个文件失败不丢弃其他成功输入，失败提示含文件名；刷新恢复只读成功
  Asset ID，不再次上传。素材库仍先上传再 Attach；关联失败尝试受限清理，清理失败必须单独显示，
  不能把已经上传成功误称原文件上传失败。
- 413（包括 HTML 代理响应）明确大小限制，409团队缺省提示选团队，403模块拒绝提示授权，超时明确
  结果未确认并提示先刷新检查；Attach/Cleanup 阶段、受控错误码及存在时的 requestId 保留。不展示
  原始代理 HTML、存储路径或秘密。
