import type { AssetReadDto } from '@/entities/asset/api/contracts'
import type { PageDto } from '@/shared/api'

export type GenerationMode = 'NORMAL_GENERATION' | 'STYLE_REPLICATION'
export type GenerationWorkMode = 'INSTANT' | 'BATCH'
export type GenerationOutputRole = 'MAIN_IMAGE' | 'DETAIL_IMAGE'
export type GenerationOutputFormat = 'SINGLE' | 'COLLAGE_2X2'
export type GenerationSize = '1:1' | '3:4' | '4:3' | '16:9'
export type MaterialRole = 'PRODUCT_SOURCE' | 'STYLE_REFERENCE' | 'AI_OUTPUT'
export type GenerationJobStatus =
  'PENDING' | 'RUNNING' | 'SUCCESS' | 'PARTIAL_FAILED' | 'FAILED'
export type GenerationItemStatus = 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED'

export interface AiModelCatalogReadDto {
  model_id: string
  model_code: string
  display_name: string
  capabilities: GenerationMode[]
  max_input_images: number
  supported_sizes: GenerationSize[]
  supported_resolutions: Array<'1k' | '2k' | '4k'>
  is_default: boolean
}

export interface PromptTemplateReadDto {
  prompt_template_id: string
  template_group_id: string
  name: string
  enabled: boolean
  output_role: GenerationOutputRole
  output_format: GenerationOutputFormat
  size: GenerationSize
  count: number
  variables: string[]
  prompt: string
  sort_order: number
  created_at: string
  updated_at: string
}

export interface TemplateGroupSummaryReadDto {
  template_group_id: string
  name: string
  mode: GenerationMode
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface TemplateGroupReadDto extends TemplateGroupSummaryReadDto {
  prompt_templates: PromptTemplateReadDto[]
}

export interface TemplateGroupCreateDto {
  name: string
  mode: GenerationMode
  enabled?: boolean
}

export interface TemplateGroupUpdateDto {
  name?: string
  enabled?: boolean
}

export interface PromptTemplateCreateDto {
  name: string
  enabled: boolean
  output_role: GenerationOutputRole
  output_format: GenerationOutputFormat
  size: GenerationSize
  count: number
  variables: string[]
  prompt: string
}

export type PromptTemplateUpdateDto = Omit<
  PromptTemplateCreateDto,
  'output_role'
>

export interface MaterialGroupAssetReadDto {
  role: MaterialRole
  created_at: string
  asset: AssetReadDto
}

export interface MaterialGroupTemplateBindingReadDto {
  material_group_id: string
  template_group_id: string
  generation_mode: GenerationMode
  position: number
  created_at: string
}

export interface ProductMaterialGroupSummaryReadDto {
  material_group_id: string
  name: string
  enabled: boolean
  normal_generation_enabled: boolean
  style_replication_enabled: boolean
  created_at: string
  updated_at: string
}

export interface ProductMaterialGroupReadDto extends ProductMaterialGroupSummaryReadDto {
  assets: MaterialGroupAssetReadDto[]
  template_bindings: MaterialGroupTemplateBindingReadDto[]
}

export interface ProductMaterialGroupCreateDto {
  name: string
  enabled?: boolean
  normal_generation_enabled?: boolean
  style_replication_enabled?: boolean
}

export interface ProductMaterialGroupUpdateDto {
  name?: string
  enabled?: boolean
  normal_generation_enabled?: boolean
  style_replication_enabled?: boolean
}

export interface GenerationItemAssetReadDto {
  input_role: 'PRODUCT_SOURCE' | 'STYLE_REFERENCE'
  position: number
  asset: AssetReadDto
}

export interface GenerationItemReadDto {
  generation_item_id: string
  position: number
  status: GenerationItemStatus
  final_prompt: string
  output_role: GenerationOutputRole
  output_format: GenerationOutputFormat
  size: GenerationSize
  source_product_position: number | null
  source_template_group_position: number | null
  source_prompt_template_position: number | null
  output_ordinal: number
  source_product_material_group_id: string | null
  source_template_group_id: string | null
  source_prompt_template_id: string | null
  product_name_snapshot: string | null
  template_group_name_snapshot: string | null
  prompt_template_name_snapshot: string | null
  attempt_count: number
  last_failure_code: string | null
  last_failure_message: string | null
  last_failed_at: string | null
  started_at: string | null
  finished_at: string | null
  archived_material_group_id: string | null
  archived_material_group_name_snapshot: string | null
  archived_at: string | null
  input_assets: GenerationItemAssetReadDto[]
  output_asset: AssetReadDto | null
}

export interface GenerationCountsReadDto {
  total_count: number
  pending_count: number
  running_count: number
  success_count: number
  failed_count: number
}

export interface GenerationJobSummaryReadDto extends GenerationCountsReadDto {
  generation_job_id: string
  model_id: string
  model_code: string
  model_display_name: string
  work_mode: GenerationWorkMode
  mode: GenerationMode
  compress_output_under_1000kb: boolean
  status: GenerationJobStatus
  input_summary: { count: number; primary_name: string | null }
  created_by_display_name: string
  created_at: string
  updated_at: string
}

export interface GenerationJobReadDto extends GenerationJobSummaryReadDto {
  submission_key: string
  started_at: string | null
  finished_at: string | null
  items: GenerationItemReadDto[]
}

export interface InstantGenerationSubmitDto {
  work_mode: 'INSTANT'
  submission_key: string
  model_id: string
  mode: GenerationMode
  product_asset_ids: string[]
  reference_asset_ids: string[]
  prompt_template_id?: string | null
  prompt: string
  output_format: GenerationOutputFormat
  size: GenerationSize
  count: number
  compress_output_under_1000kb: boolean
}

export interface BatchGenerationSubmitDto {
  work_mode: 'BATCH'
  submission_key: string
  model_id: string
  mode: GenerationMode
  product_scope: 'ALL_ENABLED' | 'SELECTED'
  selected_product_ids: string[]
  template_source: 'PRODUCT_CONFIGURED' | 'CURRENT_SELECTION'
  selected_template_group_ids: string[]
  output_range: 'ALL' | GenerationOutputRole
  compress_output_under_1000kb: boolean
}

export type GenerationSubmitDto =
  InstantGenerationSubmitDto | BatchGenerationSubmitDto

export interface GenerationRetryRequestDto {
  items: Array<{ item_id: string; expected_attempt_count: number }>
}

export type TemplateGroupPageDto = PageDto<TemplateGroupSummaryReadDto>
export type ProductMaterialGroupPageDto =
  PageDto<ProductMaterialGroupSummaryReadDto>
export type GenerationJobPageDto = PageDto<GenerationJobSummaryReadDto>
