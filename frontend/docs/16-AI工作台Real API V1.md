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

## 4. Visual Mock Boundary

Visual Mock 仅在 Development 且查询参数精确为 `visualMock=1` 时动态加载，用于冻结视觉与交互测试。Production Build 默认且唯一运行 Real API 页面，不提供 Fixture fallback。

页面继续复用 AI Module Shell、Shared 状态组件、表单控件、分页和工作台结构。平台展示统一复用 `PlatformDisplay` 的固定图标槽与左对齐名称，不在业务页面分别补 margin。
