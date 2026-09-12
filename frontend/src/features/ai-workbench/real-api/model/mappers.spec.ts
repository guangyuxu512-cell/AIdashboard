import { describe, expect, it } from 'vitest'

import type {
  GenerationItemReadDto,
  GenerationJobReadDto,
  GenerationJobStatus,
  ProductMaterialGroupReadDto,
  TemplateGroupReadDto,
} from '@/entities/ai-workbench'

import {
  mapGenerationRecord,
  mapGenerationRecordSummary,
  mapInstantExecution,
  mapGenerationProduct,
  mapProductMaterialGroup,
  mapTemplateGroup,
  mapWorkbenchModel,
} from './mappers'

function item(
  position: number,
  status: GenerationItemReadDto['status'],
): GenerationItemReadDto {
  const successful = status === 'SUCCESS'
  const failed = status === 'FAILED'
  return {
    generation_item_id: `item-${position}`,
    position,
    status,
    final_prompt: '完整提示词',
    output_role: 'MAIN_IMAGE',
    output_format: 'SINGLE',
    size: '1:1',
    source_product_position: null,
    source_template_group_position: null,
    source_prompt_template_position: null,
    output_ordinal: position,
    source_product_material_group_id: null,
    source_template_group_id: null,
    source_prompt_template_id: null,
    product_name_snapshot: null,
    template_group_name_snapshot: null,
    prompt_template_name_snapshot: null,
    attempt_count: 1,
    last_failure_code: failed ? 'PROVIDER_ERROR' : null,
    last_failure_message: failed ? '生成失败' : null,
    last_failed_at: failed ? '2026-09-06T00:01:00Z' : null,
    started_at: status === 'PENDING' ? null : '2026-09-06T00:00:10Z',
    finished_at: successful || failed ? '2026-09-06T00:01:00Z' : null,
    archived_material_group_id: successful ? 'material-1' : null,
    archived_material_group_name_snapshot: successful ? '手机支架' : null,
    archived_at: successful ? '2026-09-06T00:02:00Z' : null,
    input_assets: [],
    output_asset: successful
      ? {
          asset_id: `asset-${position}`,
          media_type: 'image',
          original_filename: `result-${position}.png`,
          content_type: 'image/png',
          size_bytes: 128,
          sha256: 'a'.repeat(64),
          source_type: 'ai_generated',
          created_at: '2026-09-06T00:01:00Z',
        }
      : null,
  }
}

function job(
  status: GenerationJobStatus,
  itemStatuses: GenerationItemReadDto['status'][],
): GenerationJobReadDto {
  const items = itemStatuses.map((value, index) => item(index, value))
  return {
    generation_job_id: `job-${status}`,
    submission_key: `submission-${status}`,
    model_id: 'model-1',
    model_code: 'gpt-image-2',
    model_display_name: 'GPT Image 2',
    work_mode: 'INSTANT',
    mode: 'NORMAL_GENERATION',
    compress_output_under_1000kb: false,
    status,
    input_summary: { count: 1, primary_name: '商品图.png' },
    created_by_display_name: '测试用户',
    created_at: '2026-09-06T00:00:00Z',
    updated_at: '2026-09-06T00:01:00Z',
    started_at: status === 'PENDING' ? null : '2026-09-06T00:00:10Z',
    finished_at:
      status === 'SUCCESS' || status === 'PARTIAL_FAILED' || status === 'FAILED'
        ? '2026-09-06T00:01:00Z'
        : null,
    total_count: items.length,
    pending_count: items.filter((value) => value.status === 'PENDING').length,
    running_count: items.filter((value) => value.status === 'RUNNING').length,
    success_count: items.filter((value) => value.status === 'SUCCESS').length,
    failed_count: items.filter((value) => value.status === 'FAILED').length,
    items,
  }
}

describe('AI Workbench real API mappers', () => {
  it('maps the model catalog capability facts without a frontend model constant', () => {
    expect(
      mapWorkbenchModel({
        model_id: 'model-1',
        model_code: 'gpt-image-2',
        display_name: 'GPT Image 2',
        capabilities: ['NORMAL_GENERATION', 'STYLE_REPLICATION'],
        max_input_images: 6,
        supported_sizes: ['1:1', '3:4', '4:3', '16:9'],
        supported_resolutions: ['1k'],
        is_default: true,
      }),
    ).toEqual({
      id: 'model-1',
      code: 'gpt-image-2',
      name: 'GPT Image 2',
      capabilities: ['NORMAL_GENERATION', 'STYLE_REPLICATION'],
      maxInputImages: 6,
      supportedSizes: ['1:1', '3:4', '4:3', '16:9'],
      supportedResolutions: ['1k'],
      isDefault: true,
    })
  })

  it('maps template and material management facts from backend DTOs', () => {
    const templateGroup: TemplateGroupReadDto = {
      template_group_id: 'group-1',
      name: '电商主图',
      mode: 'NORMAL_GENERATION',
      enabled: true,
      created_at: '2026-09-06T00:00:00Z',
      updated_at: '2026-09-06T00:00:00Z',
      prompt_templates: [
        {
          prompt_template_id: 'template-1',
          template_group_id: 'group-1',
          name: '纯白主图',
          enabled: true,
          output_role: 'MAIN_IMAGE',
          output_format: 'SINGLE',
          size: '1:1',
          count: 1,
          variables: [],
          prompt: '纯白背景',
          sort_order: 0,
          created_at: '2026-09-06T00:00:00Z',
          updated_at: '2026-09-06T00:00:00Z',
        },
      ],
    }
    const materialGroup: ProductMaterialGroupReadDto = {
      material_group_id: 'material-1',
      name: '手机支架',
      enabled: true,
      normal_generation_enabled: true,
      style_replication_enabled: false,
      created_at: '2026-09-06T00:00:00Z',
      updated_at: '2026-09-06T00:00:00Z',
      assets: [
        {
          role: 'PRODUCT_SOURCE',
          created_at: '2026-09-06T00:00:00Z',
          asset: {
            asset_id: 'asset-1',
            media_type: 'image',
            original_filename: 'product.png',
            content_type: 'image/png',
            size_bytes: 256,
            sha256: 'b'.repeat(64),
            source_type: 'upload',
            created_at: '2026-09-06T00:00:00Z',
          },
        },
        {
          role: 'AI_OUTPUT',
          created_at: '2026-09-06T00:00:00Z',
          asset: {
            asset_id: 'asset-output-1',
            media_type: 'image',
            original_filename: 'generated.png',
            content_type: 'image/png',
            size_bytes: 512,
            sha256: 'c'.repeat(64),
            source_type: 'ai_generated',
            created_at: '2026-09-06T00:00:00Z',
          },
        },
      ],
      template_bindings: [
        {
          material_group_id: 'material-1',
          template_group_id: 'group-1',
          generation_mode: 'NORMAL_GENERATION',
          position: 0,
          created_at: '2026-09-06T00:00:00Z',
        },
      ],
    }

    expect(mapTemplateGroup(templateGroup)).toMatchObject({
      id: 'group-1',
      templates: [{ id: 'template-1', outputRole: 'MAIN_IMAGE' }],
    })
    expect(mapProductMaterialGroup(materialGroup)).toMatchObject({
      id: 'material-1',
      normalTemplateGroupIds: ['group-1'],
      styleReplicationTemplateGroupIds: [],
      assets: [
        { assetId: 'asset-1', role: 'PRODUCT_SOURCE' },
        { assetId: 'asset-output-1', role: 'AI_OUTPUT' },
      ],
    })
    expect(mapGenerationProduct(materialGroup).assets).toEqual([
      expect.objectContaining({ id: 'asset-1', role: 'PRODUCT_SOURCE' }),
      expect.objectContaining({ id: 'asset-output-1', role: 'AI_OUTPUT' }),
    ])
  })

  it.each([
    ['PENDING', 'QUEUED'],
    ['RUNNING', 'RUNNING'],
    ['SUCCESS', 'SUCCESS'],
    ['PARTIAL_FAILED', 'PARTIAL_FAILED'],
    ['FAILED', 'FAILED'],
  ] as const)('maps %s records to %s', (backendStatus, viewStatus) => {
    const itemStatuses: GenerationItemReadDto['status'][] =
      backendStatus === 'SUCCESS'
        ? ['SUCCESS']
        : backendStatus === 'PARTIAL_FAILED'
          ? ['SUCCESS', 'FAILED']
          : backendStatus === 'FAILED'
            ? ['FAILED']
            : backendStatus === 'RUNNING'
              ? ['RUNNING']
              : ['PENDING']
    const dto = job(backendStatus, itemStatuses)

    expect(mapGenerationRecordSummary(dto)).toMatchObject({
      status: viewStatus,
      summary: expect.stringContaining('GPT Image 2'),
    })
    expect(mapGenerationRecord(dto)).toMatchObject({ status: viewStatus })
  })

  it('uses only formal Asset content URLs for successful results', () => {
    const dto = job('SUCCESS', ['SUCCESS'])
    const execution = mapInstantExecution(dto)

    expect(execution).toMatchObject({
      status: 'SUCCESS',
      successCount: 1,
      results: [
        {
          assetId: 'asset-0',
          previewUrl: '/api/v1/assets/asset-0/content',
          thumbnailUrl: '/api/v1/assets/asset-0/thumbnail',
        },
      ],
    })
    expect(execution.results[0]).not.toHaveProperty('savedToProductId')
    expect(JSON.stringify(execution)).not.toContain('toapis')
    expect(JSON.stringify(execution)).not.toContain('providerUrl')
  })
})
