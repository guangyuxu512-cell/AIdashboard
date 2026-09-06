# AI Model Management V1

> - 状态：`IMPLEMENTED`
> - 日期：2026-09-06
> - Migration：`20260906_0031_ai_model_management_v1`

## 1. Scope

AI Model Management V1 建立一个全局模型目录，为系统管理员维护模型能力，并为 AI 工作台提供启用模型读取边界。V1 只有 `ai_models` 一个实体，不建立 Provider 表、Secret 管理、价格、余额、健康评分、权重、优先级、Team Binding 或版本历史。

模型目录尚不参与 Generation Submit 或 Provider 执行选择。现有 ToAPIs Adapter 继续读取服务器配置；GenerationJob、GenerationItem、GenerationProviderExecution 与 Asset Schema 均不改变。

## 2. Model Catalog

`ai_models` 保存：

- `model_id`：稳定 UUID 主键；
- `display_name`：管理端名称；
- `model_code`：Provider 下的稳定业务标识，创建后不可修改；
- `provider_code`：V1 仅允许 `toapis`，创建后不可修改；
- `enabled / is_default`：可用性与全局默认状态；
- `capabilities`：只允许 `NORMAL_GENERATION / STYLE_REPLICATION`；
- `max_input_images`：最大输入图片数；
- `supported_sizes`：只允许 `1:1 / 3:4 / 4:3 / 16:9`；
- `supported_resolutions`：只允许 `1k / 2k / 4k`；
- `created_at / updated_at`：标准时间字段。

Quality 继续使用既有服务器运行配置，不进入目录。目录不保存 API Key、Base URL 或 Provider Payload。

0031 初始化唯一真实模型 `GPT Image 2 / gpt-image-2 / toapis`，启用并设为默认，支持两项 Capability、6 张输入、四种尺寸和三档 Resolution；不初始化 Demo 模型。

## 3. Default Rules

- `is_default=true` 必须同时 `enabled=true`；
- 部分唯一索引保证同一时间最多一个默认模型；
- 设置新默认时，Service 锁定目录，在同一事务中先清除旧默认再设置新默认；
- 当前默认模型不能直接停用或清除默认状态，管理员必须先将另一个已启用模型设为默认；
- 系统不自动猜测替代默认模型；
- V1 不提供 Hard Delete。

## 4. API

管理 API 统一位于 `/api/v1/ai-models`，要求 Human Auth 与当前 Team Context 的 `access_admin`：

- `GET /api/v1/ai-models`：列表；
- `POST /api/v1/ai-models`：创建；
- `GET /api/v1/ai-models/{model_id}`：详情；
- `PATCH /api/v1/ai-models/{model_id}`：修改展示、启停与能力字段；
- `POST /api/v1/ai-models/{model_id}/default`：设置默认。

业务目录 API 为 `GET /api/v1/ai-workbench/models`，要求 Human Auth 与 `ai-workbench` Module Access。它只返回启用模型的 `model_id / model_code / display_name / capabilities / max_input_images / supported_sizes / supported_resolutions / is_default`，不返回 `provider_code`、Secret、Base URL 或内部 Provider 配置。

实现固定遵守 `API → AiModelCatalogService → AiModelRepository → PostgreSQL`。Provider 支持校验只是 V1 的 `toapis` 白名单，不扩建 Registry、Engine 或动态 Plugin。

## 5. Migration

`20260906_0031_ai_model_management_v1` 以 `20260905_0030_ai_provider_v1` 为唯一父 Revision，只创建 `ai_models`、约束、唯一索引和正式 GPT Image 2 初始化记录。Upgrade / Downgrade 仅允许在登记的 `control_center_feat_ai_model_management` Feature DB 验证；不得写 Main 或 Integration DB。
