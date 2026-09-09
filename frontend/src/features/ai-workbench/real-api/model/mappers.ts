import {
  getAssetContentUrl,
  getAssetThumbnailUrl,
} from '@/entities/asset/api/asset-api'
import type {
  AiModelCatalogReadDto,
  GenerationItemReadDto,
  GenerationJobReadDto,
  GenerationJobSummaryReadDto,
  GenerationJobStatus,
  ProductMaterialGroupReadDto,
  PromptTemplateReadDto,
  TemplateGroupReadDto,
} from '@/entities/ai-workbench'

import type {
  MaterialAssetReference,
  ProductMaterialGroup,
} from '../../assets/model/types'
import { createBatchExecutionView } from '../../generation/model/batch-execution'
import { createInstantExecutionView } from '../../generation/model/instant-execution'
import type {
  BatchExecutionView,
  BatchProductResultView,
  GenerationExecutionResultView,
  GenerationProductView,
  GenerationRecordStatus,
  GenerationRecordView,
  GenerationSourceImageView,
  GenerationTemplateGroupView,
  InstantExecutionView,
} from '../../generation/model/types'
import type { PromptTemplate, TemplateGroup } from '../../templates/model/types'

export interface WorkbenchModelView {
  id: string
  code: string
  name: string
  capabilities: AiModelCatalogReadDto['capabilities']
  maxInputImages: number
  supportedSizes: AiModelCatalogReadDto['supported_sizes']
  supportedResolutions: AiModelCatalogReadDto['supported_resolutions']
  isDefault: boolean
}

export function mapWorkbenchModel(
  dto: AiModelCatalogReadDto,
): WorkbenchModelView {
  return {
    id: dto.model_id,
    code: dto.model_code,
    name: dto.display_name,
    capabilities: [...dto.capabilities],
    maxInputImages: dto.max_input_images,
    supportedSizes: [...dto.supported_sizes],
    supportedResolutions: [...dto.supported_resolutions],
    isDefault: dto.is_default,
  }
}

export function mapPromptTemplate(dto: PromptTemplateReadDto): PromptTemplate {
  return {
    id: dto.prompt_template_id,
    name: dto.name,
    enabled: dto.enabled,
    outputRole: dto.output_role,
    outputFormat: dto.output_format,
    size: dto.size,
    count: dto.count,
    variables: [...dto.variables],
    prompt: dto.prompt,
    sortOrder: dto.sort_order,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  }
}

export function mapTemplateGroup(dto: TemplateGroupReadDto): TemplateGroup {
  return {
    id: dto.template_group_id,
    name: dto.name,
    mode: dto.mode,
    enabled: dto.enabled,
    templates: dto.prompt_templates.map(mapPromptTemplate),
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  }
}

function sourceType(
  value: 'upload' | 'ai_generated' | 'imported',
): MaterialAssetReference['sourceType'] {
  if (value === 'ai_generated') return 'AI_GENERATION'
  if (value === 'imported') return 'MATERIAL_IMPORT'
  return 'LOCAL_UPLOAD'
}

export function mapProductMaterialGroup(
  dto: ProductMaterialGroupReadDto,
): ProductMaterialGroup {
  return {
    id: dto.material_group_id,
    name: dto.name,
    enabled: dto.enabled,
    normalGenerationEnabled: dto.normal_generation_enabled,
    styleReplicationEnabled: dto.style_replication_enabled,
    normalTemplateGroupIds: dto.template_bindings
      .filter((binding) => binding.generation_mode === 'NORMAL_GENERATION')
      .sort((left, right) => left.position - right.position)
      .map((binding) => binding.template_group_id),
    styleReplicationTemplateGroupIds: dto.template_bindings
      .filter((binding) => binding.generation_mode === 'STYLE_REPLICATION')
      .sort((left, right) => left.position - right.position)
      .map((binding) => binding.template_group_id),
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
    assets: dto.assets.map((link) => ({
      assetId: link.asset.asset_id,
      name: link.asset.original_filename,
      mediaType: link.asset.content_type,
      sourceType: sourceType(link.asset.source_type),
      role: link.role,
      previewUrl: getAssetContentUrl(link.asset.asset_id),
      thumbnailUrl: getAssetThumbnailUrl(link.asset.asset_id),
      sizeBytes: link.asset.size_bytes,
    })),
  }
}

export function mapGenerationProduct(
  dto: ProductMaterialGroupReadDto,
): GenerationProductView {
  const product = mapProductMaterialGroup(dto)
  return {
    id: product.id,
    name: product.name,
    enabled: product.enabled,
    normalGenerationEnabled: product.normalGenerationEnabled,
    styleReplicationEnabled: product.styleReplicationEnabled,
    normalTemplateGroupIds: [...product.normalTemplateGroupIds],
    styleReplicationTemplateGroupIds: [
      ...product.styleReplicationTemplateGroupIds,
    ],
    assets: product.assets.map((asset) => ({
      id: asset.assetId,
      name: asset.name,
      previewUrl: asset.previewUrl,
      thumbnailUrl: asset.thumbnailUrl,
      role:
        asset.role === 'STYLE_REFERENCE' ? 'STYLE_REFERENCE' : 'PRODUCT_SOURCE',
      sourceType: 'ASSET_LIBRARY',
      productId: product.id,
      productName: product.name,
    })),
  }
}

export function mapGenerationTemplateGroup(
  dto: TemplateGroupReadDto,
): GenerationTemplateGroupView {
  return {
    id: dto.template_group_id,
    name: dto.name,
    mode: dto.mode,
    enabled: dto.enabled,
    templates: dto.prompt_templates.map((template) => ({
      id: template.prompt_template_id,
      groupId: dto.template_group_id,
      groupName: dto.name,
      name: template.name,
      mode: dto.mode,
      enabled: template.enabled,
      outputRole: template.output_role,
      outputFormat: template.output_format,
      size: template.size,
      count: template.count,
      prompt: template.prompt,
      sortOrder: template.sort_order,
    })),
  }
}

function executionResult(
  item: GenerationItemReadDto,
): GenerationExecutionResultView {
  const status = item.status === 'PENDING' ? 'WAITING' : item.status
  return {
    id: item.generation_item_id,
    slotIndex: item.position,
    name: item.output_asset?.original_filename,
    status,
    previewUrl: item.output_asset
      ? getAssetContentUrl(item.output_asset.asset_id)
      : undefined,
    thumbnailUrl: item.output_asset
      ? getAssetThumbnailUrl(item.output_asset.asset_id)
      : undefined,
    assetId: item.output_asset?.asset_id,
    outputRole: item.output_role,
    size: item.size,
    errorCode: item.last_failure_code ?? undefined,
    errorMessage: item.last_failure_message ?? undefined,
  }
}

export function mapInstantExecution(
  dto: GenerationJobReadDto,
): InstantExecutionView {
  return createInstantExecutionView({
    id: dto.generation_job_id,
    results: dto.items.map(executionResult),
  })
}

export function mapBatchExecution(
  dto: GenerationJobReadDto,
): BatchExecutionView {
  const products = new Map<
    string,
    {
      productId: string
      productName: string
      groups: Map<
        string,
        {
          templateGroupId: string
          templateGroupName: string
          templates: Map<
            string,
            {
              templateId: string
              templateName: string
              outputRole: 'MAIN_IMAGE' | 'DETAIL_IMAGE'
              results: GenerationExecutionResultView[]
            }
          >
        }
      >
    }
  >()

  for (const item of dto.items) {
    const productId = item.source_product_material_group_id ?? 'removed-product'
    const groupId = item.source_template_group_id ?? 'removed-template-group'
    const templateId = item.source_prompt_template_id ?? item.generation_item_id
    const product = products.get(productId) ?? {
      productId,
      productName: item.product_name_snapshot ?? '已删除产品',
      groups: new Map(),
    }
    products.set(productId, product)
    const group = product.groups.get(groupId) ?? {
      templateGroupId: groupId,
      templateGroupName: item.template_group_name_snapshot ?? '已删除模板组',
      templates: new Map(),
    }
    product.groups.set(groupId, group)
    const template = group.templates.get(templateId) ?? {
      templateId,
      templateName: item.prompt_template_name_snapshot ?? '模板',
      outputRole: item.output_role,
      results: [],
    }
    group.templates.set(templateId, template)
    template.results.push(executionResult(item))
  }

  return createBatchExecutionView({
    id: dto.generation_job_id,
    products: [...products.values()].map((product) => ({
      productId: product.productId,
      productName: product.productName,
      templateGroups: [...product.groups.values()].map((group) => ({
        templateGroupId: group.templateGroupId,
        templateGroupName: group.templateGroupName,
        templates: [...group.templates.values()],
      })),
    })),
  })
}

function recordStatus(status: GenerationJobStatus): GenerationRecordStatus {
  return status === 'PENDING' ? 'QUEUED' : status
}

export function mapGenerationRecordSummary(
  dto: GenerationJobSummaryReadDto,
): GenerationRecordView {
  const base = {
    id: dto.generation_job_id,
    sourceType: dto.work_mode,
    mode: dto.mode,
    status: recordStatus(dto.status),
    createdAt: dto.created_at,
    createdBy: dto.created_by_display_name,
    summary: `${dto.model_display_name} · ${dto.input_summary.primary_name ?? `${dto.total_count} 个生成项`}`,
    resultSummary: `成功 ${dto.success_count} · 失败 ${dto.failed_count}`,
  }
  return dto.work_mode === 'INSTANT'
    ? {
        ...base,
        detail: {
          kind: 'INSTANT',
          executionId: dto.generation_job_id,
          inputSlots: [],
          templateId: null,
          templateName: null,
          effectiveConfig: {
            prompt: '',
            outputFormat: 'SINGLE',
            size: '1:1',
            count: dto.total_count,
          },
          results: [],
        },
      }
    : {
        ...base,
        detail: {
          kind: 'BATCH',
          productCount: 0,
          templateGroupCount: 0,
          generationItemCount: dto.total_count,
          successCount: dto.success_count,
          failedCount: dto.failed_count,
          results: [],
        },
      }
}

function sourceImage(
  item: GenerationItemReadDto,
  role: 'PRODUCT_SOURCE' | 'STYLE_REFERENCE',
): GenerationSourceImageView[] {
  return item.input_assets
    .filter((link) => link.input_role === role)
    .map((link) => ({
      id: link.asset.asset_id,
      name: link.asset.original_filename,
      previewUrl: getAssetContentUrl(link.asset.asset_id),
      thumbnailUrl: getAssetThumbnailUrl(link.asset.asset_id),
      role,
      sourceType: 'ASSET_LIBRARY',
    }))
}

function batchRecordResults(
  dto: GenerationJobReadDto,
): BatchProductResultView[] {
  return mapBatchExecution(dto).products.map((product) => ({
    productId: product.productId,
    productName: product.productName,
    groups: product.templateGroups.map((group) => ({
      groupId: group.templateGroupId,
      groupName: group.templateGroupName,
      templates: group.templates.map((template) => ({
        templateId: template.templateId,
        templateName: template.templateName,
        outputRole: template.outputRole,
        results: template.results
          .filter(
            (result) =>
              result.status === 'SUCCESS' || result.status === 'FAILED',
          )
          .map((result) => ({
            id: result.id,
            name: result.name ?? template.templateName,
            previewUrl: result.previewUrl ?? '',
            thumbnailUrl: result.thumbnailUrl,
            status: result.status as 'SUCCESS' | 'FAILED',
            outputRole: result.outputRole ?? template.outputRole,
            size: result.size ?? '1:1',
          })),
      })),
    })),
  }))
}

export function mapGenerationRecord(
  dto: GenerationJobReadDto,
): GenerationRecordView {
  const first = dto.items[0]
  const summary =
    dto.work_mode === 'INSTANT'
      ? (first?.final_prompt ?? '即时生成')
      : `${dto.input_summary.primary_name ?? '批量任务'} · ${dto.total_count} 项`
  const base = {
    id: dto.generation_job_id,
    sourceType: dto.work_mode,
    mode: dto.mode,
    status: recordStatus(dto.status),
    createdAt: dto.created_at,
    createdBy: dto.created_by_display_name,
    summary: `${dto.model_display_name} · ${summary}`,
    resultSummary: `成功 ${dto.success_count} · 失败 ${dto.failed_count}`,
  }
  if (dto.work_mode === 'INSTANT') {
    const count = dto.items.length
    return {
      ...base,
      detail: {
        kind: 'INSTANT',
        executionId: dto.generation_job_id,
        inputSlots: first
          ? [
              {
                key: 'PRODUCT_IMAGES' as const,
                label: '商品图片',
                images: sourceImage(first, 'PRODUCT_SOURCE'),
              },
              ...(dto.mode === 'STYLE_REPLICATION'
                ? [
                    {
                      key: 'REFERENCE_IMAGES' as const,
                      label: '参考图片',
                      images: sourceImage(first, 'STYLE_REFERENCE'),
                    },
                  ]
                : []),
            ]
          : [],
        templateId: first?.source_prompt_template_id ?? null,
        templateName: first?.prompt_template_name_snapshot ?? null,
        effectiveConfig: {
          prompt: first?.final_prompt ?? '',
          outputFormat: first?.output_format ?? 'SINGLE',
          size: first?.size ?? '1:1',
          count,
        },
        results: dto.items.map(executionResult),
      },
    }
  }
  const results = batchRecordResults(dto)
  return {
    ...base,
    detail: {
      kind: 'BATCH',
      productCount: results.length,
      templateGroupCount: new Set(
        dto.items.map((item) => item.source_template_group_id).filter(Boolean),
      ).size,
      generationItemCount: dto.total_count,
      successCount: dto.success_count,
      failedCount: dto.failed_count,
      results,
    },
  }
}
