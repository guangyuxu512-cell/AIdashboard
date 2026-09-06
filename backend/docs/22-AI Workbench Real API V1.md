# AI Workbench Real API V1

> - 状态：`IMPLEMENTED`
> - 日期：2026-09-06
> - Migration：`20260906_0032_ai_workbench_real_api_v1`
> - Contract：《18-AI Generation Execution Contract V1》

## 1. Generation Model Integration

Instant 与 Batch Submit 都必须提交 `model_id`。Service 在创建 Job 前验证模型存在、启用、支持当前 Generation Mode，并在计划展开后逐 Item 验证输入图数量与 Size。`model_id` 进入 submission fingerprint。

`GenerationJob.model_id` 是指向 `ai_models.model_id` 的非空、`ON DELETE RESTRICT` Foreign Key；`GenerationItem` 不重复保存。0032 根据唯一启用且默认的 `toapis / gpt-image-2` Catalog 记录回填历史 Job，不硬编码 Model UUID，目标记录缺失或不唯一时 Migration 失败。

Job 一经接受，执行与 Retry 始终沿用原 `model_id`。模型之后被停用只阻止新 Submit，不改变已接受任务。

## 2. Provider Routing

执行路径固定为：

```text
GenerationJob.model_id
→ AiModel.provider_code / model_code
→ provider_code = toapis
→ ToApisImageProvider(request.model_code)
```

ToAPIs Base URL、API Key、Resolution、Quality 与超时继续来自服务器配置。Model 不再由 `BACKEND_TOAPIS_MODEL_CODE` 选择。V1 不建立 Provider Routing Engine、Plugin Framework、Model Snapshot 或第二套 Registry。

## 3. Read Contract

Generation Job List 与 Detail 返回 `model_id / model_code / model_display_name`，用于工作台和生成记录展示。响应不包含 `provider_code`、Base URL、Credential、Secret 或 Provider Payload。

Backend 继续遵守 `API → GenerationService → Repository → PostgreSQL`；Asset 输出、Storage、Ownership、Retry、Archive 与 Provider Durable Intent 沿用既有 Frozen Contract。

## 4. Validation

0032 只允许在 `control_center_feat_ai_workbench_real_api` Feature DB 验证 `0031 → 0032 → 0031 → 0032`，并确认 Single Head、历史 Job 回填和非空 Foreign Key。Production、Main 与 Integration DB 不在 Feature 验证范围内。
