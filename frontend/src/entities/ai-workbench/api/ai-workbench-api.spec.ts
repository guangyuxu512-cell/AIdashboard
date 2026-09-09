import { afterEach, describe, expect, it, vi } from 'vitest'

import { httpClient } from '@/shared/api'

import { aiWorkbenchApi } from './ai-workbench-api'

describe('AI Workbench API client', () => {
  afterEach(() => vi.restoreAllMocks())

  it('loads the enabled business model catalog from the real endpoint', async () => {
    const models = [
      {
        model_id: 'model-1',
        model_code: 'gpt-image-2',
        display_name: 'GPT Image 2',
        capabilities: ['NORMAL_GENERATION'],
        max_input_images: 6,
        supported_sizes: ['1:1'],
        supported_resolutions: ['1k'],
        is_default: true,
      },
    ]
    const get = vi.spyOn(httpClient, 'get').mockResolvedValue({ data: models })

    await expect(aiWorkbenchApi.listModels()).resolves.toBe(models)
    expect(get).toHaveBeenCalledWith('/api/v1/ai-workbench/models')
  })

  it('uses the formal TemplateGroup and PromptTemplate endpoints', async () => {
    const get = vi.spyOn(httpClient, 'get').mockResolvedValue({ data: {} })
    const post = vi.spyOn(httpClient, 'post').mockResolvedValue({ data: {} })
    const patch = vi.spyOn(httpClient, 'patch').mockResolvedValue({ data: {} })
    const put = vi.spyOn(httpClient, 'put').mockResolvedValue({ data: {} })
    const remove = vi
      .spyOn(httpClient, 'delete')
      .mockResolvedValue({ data: {} })

    await aiWorkbenchApi.listTemplateGroups({
      page: 2,
      pageSize: 20,
      search: '  商品  ',
      mode: 'NORMAL_GENERATION',
      enabled: true,
    })
    await aiWorkbenchApi.getTemplateGroup('group-1')
    await aiWorkbenchApi.createTemplateGroup({
      name: '商品模板',
      mode: 'NORMAL_GENERATION',
    })
    await aiWorkbenchApi.updateTemplateGroup('group-1', { enabled: false })
    await aiWorkbenchApi.createPromptTemplate('group-1', {
      name: '主图',
      enabled: true,
      output_role: 'MAIN_IMAGE',
      output_format: 'SINGLE',
      size: '1:1',
      count: 1,
      variables: [],
      prompt: '白色背景商品图',
    })
    await aiWorkbenchApi.updatePromptTemplate('group-1', 'template-1', {
      name: '新主图',
      enabled: true,
      output_format: 'SINGLE',
      size: '1:1',
      count: 1,
      variables: [],
      prompt: '新提示词',
    })
    await aiWorkbenchApi.duplicatePromptTemplate('group-1', 'template-1')
    await aiWorkbenchApi.reorderPromptTemplates('group-1', 'MAIN_IMAGE', [
      'template-2',
      'template-1',
    ])
    await aiWorkbenchApi.deletePromptTemplate('group-1', 'template-1')
    await aiWorkbenchApi.deleteTemplateGroup('group-1')

    expect(get).toHaveBeenNthCalledWith(
      1,
      '/api/v1/ai-workbench/template-groups',
      {
        params: {
          page: 2,
          page_size: 20,
          search: '商品',
          mode: 'NORMAL_GENERATION',
          enabled: true,
        },
      },
    )
    expect(get).toHaveBeenNthCalledWith(
      2,
      '/api/v1/ai-workbench/template-groups/group-1',
    )
    expect(post).toHaveBeenCalledWith(
      '/api/v1/ai-workbench/template-groups',
      expect.objectContaining({ name: '商品模板' }),
    )
    expect(post).toHaveBeenCalledWith(
      '/api/v1/ai-workbench/template-groups/group-1/prompt-templates',
      expect.objectContaining({ output_role: 'MAIN_IMAGE' }),
    )
    expect(post).toHaveBeenCalledWith(
      '/api/v1/ai-workbench/template-groups/group-1/prompt-templates/template-1/duplicate',
    )
    expect(patch).toHaveBeenCalledTimes(2)
    expect(put).toHaveBeenCalledWith(
      '/api/v1/ai-workbench/template-groups/group-1/prompt-templates/reorder',
      {
        output_role: 'MAIN_IMAGE',
        prompt_template_ids: ['template-2', 'template-1'],
      },
    )
    expect(remove).toHaveBeenCalledTimes(2)
  })

  it('uses the formal material group, asset and template binding endpoints', async () => {
    const get = vi.spyOn(httpClient, 'get').mockResolvedValue({ data: {} })
    const post = vi.spyOn(httpClient, 'post').mockResolvedValue({ data: {} })
    const patch = vi.spyOn(httpClient, 'patch').mockResolvedValue({ data: {} })
    const put = vi.spyOn(httpClient, 'put').mockResolvedValue({ data: {} })
    const remove = vi
      .spyOn(httpClient, 'delete')
      .mockResolvedValue({ data: {} })

    await aiWorkbenchApi.listProductMaterialGroups({
      page: 1,
      pageSize: 50,
      search: '  手机  ',
      enabled: true,
    })
    await aiWorkbenchApi.getProductMaterialGroup('material-1')
    await aiWorkbenchApi.createProductMaterialGroup({ name: '手机支架' })
    await aiWorkbenchApi.updateProductMaterialGroup('material-1', {
      style_replication_enabled: true,
    })
    await aiWorkbenchApi.attachAsset('material-1', 'asset-1', 'PRODUCT_SOURCE')
    await aiWorkbenchApi.replaceTemplateBindings(
      'material-1',
      'NORMAL_GENERATION',
      ['group-1'],
    )
    await aiWorkbenchApi.detachAsset('material-1', 'asset-1')
    await aiWorkbenchApi.deleteProductMaterialGroup('material-1')

    expect(get).toHaveBeenNthCalledWith(
      1,
      '/api/v1/ai-workbench/product-material-groups',
      {
        params: {
          page: 1,
          page_size: 50,
          search: '手机',
          enabled: true,
        },
      },
    )
    expect(post).toHaveBeenCalledWith(
      '/api/v1/ai-workbench/product-material-groups/material-1/assets',
      { asset_id: 'asset-1', role: 'PRODUCT_SOURCE' },
    )
    expect(patch).toHaveBeenCalledWith(
      '/api/v1/ai-workbench/product-material-groups/material-1',
      { style_replication_enabled: true },
    )
    expect(put).toHaveBeenCalledWith(
      '/api/v1/ai-workbench/product-material-groups/material-1/template-bindings/NORMAL_GENERATION',
      { template_group_ids: ['group-1'] },
    )
    expect(remove).toHaveBeenCalledTimes(2)
  })

  it('submits model_id and uses real polling, retry and archive endpoints', async () => {
    const submittedJob = { generation_job_id: 'job-1' }
    const post = vi
      .spyOn(httpClient, 'post')
      .mockResolvedValue({ data: submittedJob })
    const get = vi.spyOn(httpClient, 'get').mockResolvedValue({ data: {} })
    const payload = {
      work_mode: 'INSTANT' as const,
      submission_key: 'submission-1',
      model_id: 'model-1',
      mode: 'NORMAL_GENERATION' as const,
      product_asset_ids: ['asset-1'],
      reference_asset_ids: [],
      prompt: '白色背景商品图',
      output_format: 'SINGLE' as const,
      size: '1:1' as const,
      count: 1,
    }

    await expect(aiWorkbenchApi.submitGeneration(payload)).resolves.toBe(
      submittedJob,
    )
    await aiWorkbenchApi.listGenerationJobs({
      page: 1,
      pageSize: 20,
      workMode: 'INSTANT',
      mode: 'NORMAL_GENERATION',
      status: 'RUNNING',
    })
    await aiWorkbenchApi.getGenerationJob('job-1')
    await aiWorkbenchApi.retryGenerationItems('job-1', {
      items: [{ item_id: 'item-1', expected_attempt_count: 1 }],
    })
    await aiWorkbenchApi.archiveGenerationItem('job-1', 'item-1', 'material-1')

    expect(post).toHaveBeenNthCalledWith(
      1,
      '/api/v1/ai-workbench/generation-jobs',
      payload,
    )
    expect(get).toHaveBeenNthCalledWith(
      1,
      '/api/v1/ai-workbench/generation-jobs',
      {
        params: {
          page: 1,
          page_size: 20,
          work_mode: 'INSTANT',
          mode: 'NORMAL_GENERATION',
          status: 'RUNNING',
        },
      },
    )
    expect(get).toHaveBeenNthCalledWith(
      2,
      '/api/v1/ai-workbench/generation-jobs/job-1',
    )
    expect(post).toHaveBeenNthCalledWith(
      2,
      '/api/v1/ai-workbench/generation-jobs/job-1/retry-failed-items',
      { items: [{ item_id: 'item-1', expected_attempt_count: 1 }] },
    )
    expect(post).toHaveBeenNthCalledWith(
      3,
      '/api/v1/ai-workbench/generation-jobs/job-1/items/item-1/archive',
      { material_group_id: 'material-1' },
    )
  })
})
