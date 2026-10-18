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

## 5. AI 文件使用边界（2026-10-19）

AI 文件入口统一为 `/api/v1/ai-workbench/assets`：`POST` 上传、`GET /{asset_id}/content` 原图、
`GET /{asset_id}/thumbnail` 缩略图、`DELETE /{asset_id}` 未关联上传清理。全部要求当前 Human 身份及
`ai-workbench` 模块授权；复用 AssetService、AssetRead、Storage 与原错误契约，不建立另一套文件系统。
通用 `/api/v1/assets` 的列表、上传、读图、删除仍要求独立 `asset` 授权，不做模块 OR 放权。

读图、素材组 Attach、即时/批量 Submit 和 Retry 共用资格校验，先应用原 Actor/DataScope 与业务 Team
边界，再允许以下任一条件：

- 本人当前 Team 的 `UPLOAD` 图片草稿。无新增用途列，因此明确包含本人以前在其他模块上传的图片，
  不声称可以区分 AI 上传来源；空 Creator、其他人的无引用文件或生成来源不属于此例外。
- 实际可读 AI 素材组或 GenerationJob 输入/输出引用；引用必须连接真实父聚合，且父 Team 等于 Asset
  Team，再应用父资源 DataScope。停用组仍可读，解绑/删组撤销该引用，Job 历史引用继续保留。
- 已有显式 `asset` 模块授权保留原 scoped 图片输入能力；关联/Submit 仍不能跨业务 Team。

不得通过猜测同 Team UUID 再 Attach/Submit 制造读取资格。模块撤销由下一请求重新鉴权，返回受控
403；不存在与无资格统一 `ASSET_NOT_FOUND / 404`。AI 清理额外要求明确当前 Team、本人 UPLOAD 图片、
Asset 行锁且无 Task/素材组/生成输入/输出引用；有引用仍 `ASSET_IN_USE / 409`。Attach/Submit 同样持有
按 Asset UUID 稳定排序的原行锁，与清理串行，不能产生悬挂关系。

单文件真实 JPEG/PNG/WebP 校验及 **10 MiB** 大小上限仍以 Backend 为权威；两层 Nginx 请求体为 `12m`，
只给 multipart 留余量，不扩大文件上限。Backend 超限 `ASSET_TOO_LARGE / 413`，代理也可能先返回
HTML 413；TEAM_CONTEXT_REQUIRED/409、MODULE_ACCESS_DENIED/403、存储/缩略图503保持可区分。
本热修无 Schema、Migration 或生成/Provider 参数变更。
