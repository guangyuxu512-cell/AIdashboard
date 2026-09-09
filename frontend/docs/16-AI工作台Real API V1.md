# AI 工作台 Real API V1

## 1. Production Data Flow

AI 生图、素材库、模板库与生成记录的生产路由直接使用 `/api/v1/ai-workbench` 和正式 Asset API。TanStack Vue Query 负责 Catalog、列表、详情缓存与短轮询，页面状态只组合 Backend DTO，不在 Frontend 模拟生成成功。

```text
Model / Template / Material Catalog
→ explicit model_id Submit
→ GenerationJob 202
→ Job Detail Polling
→ GenerationItem + Asset
→ Result / Record / Retry / Archive
```

模型下拉框只展示支持当前 Mode 的启用模型，优先选择 `is_default=true`，并使用 `max_input_images / supported_sizes` 约束输入与尺寸。Backend 始终是最终校验边界。

## 2. Management Pages

- 模板库使用正式 TemplateGroup 与 PromptTemplate 列表、详情、新增、编辑、删除、复制、排序和启停 API。
- 素材库使用正式 ProductMaterialGroup、Asset 上传/读取、Attach/Detach、Role 与 Template Binding API。
- 受保护图片通过共享 Human Request Context 获取 Blob，再创建页面生命周期内的 Object URL；Provider URL 不进入页面状态。
- 生成记录以 GenerationJob 为唯一事实来源，支持 Work Mode、Mode、Status 与分页。Real API 没有搜索 Contract，因此生产页面不展示 Mock 搜索框。

## 3. Polling And Terminal States

Job Detail 在 `PENDING / RUNNING` 时短轮询；`SUCCESS / PARTIAL_FAILED / FAILED` 立即停止。记录列表仅在当前页存在非终态 Job 时轮询。失败重试与即时结果归档都调用 Backend 正式 API，Frontend 不自行改写 Item 状态。

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

## 5. Visual Mock Boundary

Visual Mock 仅在 Development 且查询参数精确为 `visualMock=1` 时动态加载，用于冻结视觉与交互测试。Production Build 默认且唯一运行 Real API 页面，不提供 Fixture fallback。

页面继续复用 AI Module Shell、Shared 状态组件、表单控件、分页和工作台结构。平台展示统一复用 `PlatformDisplay` 的固定图标槽与左对齐名称，不在业务页面分别补 margin。
