import { httpClient } from '@/shared/api'

import type {
  AiModelCatalogReadDto,
  BatchGenerationSubmitDto,
  GenerationJobPageDto,
  GenerationJobReadDto,
  GenerationJobStatus,
  GenerationMode,
  GenerationRetryRequestDto,
  InstantGenerationSubmitDto,
  MaterialRole,
  ProductMaterialGroupCreateDto,
  ProductMaterialGroupPageDto,
  ProductMaterialGroupReadDto,
  ProductMaterialGroupUpdateDto,
  PromptTemplateCreateDto,
  PromptTemplateUpdateDto,
  TemplateGroupCreateDto,
  TemplateGroupPageDto,
  TemplateGroupReadDto,
  TemplateGroupUpdateDto,
} from './contracts'

const basePath = '/api/v1/ai-workbench'

export interface PageQuery {
  page: number
  pageSize: number
}

export interface TemplateGroupListQuery extends PageQuery {
  search?: string
  mode?: GenerationMode
  enabled?: boolean
}

export interface ProductMaterialGroupListQuery extends PageQuery {
  search?: string
  enabled?: boolean
}

export interface GenerationJobListQuery extends PageQuery {
  workMode?: 'INSTANT' | 'BATCH'
  mode?: GenerationMode
  status?: GenerationJobStatus
}

function pageParams(query: PageQuery): Record<string, unknown> {
  return { page: query.page, page_size: query.pageSize }
}

export const aiWorkbenchApi = {
  async listModels(): Promise<AiModelCatalogReadDto[]> {
    const response = await httpClient.get<AiModelCatalogReadDto[]>(
      `${basePath}/models`,
    )
    return response.data
  },

  async listTemplateGroups(
    query: TemplateGroupListQuery,
  ): Promise<TemplateGroupPageDto> {
    const response = await httpClient.get<TemplateGroupPageDto>(
      `${basePath}/template-groups`,
      {
        params: {
          ...pageParams(query),
          search: query.search?.trim() || undefined,
          mode: query.mode,
          enabled: query.enabled,
        },
      },
    )
    return response.data
  },
  async listAllTemplateGroups(
    query: Omit<TemplateGroupListQuery, 'page' | 'pageSize'> = {},
  ): Promise<TemplateGroupPageDto['items']> {
    const first = await this.listTemplateGroups({
      ...query,
      page: 1,
      pageSize: 100,
    })
    const pages = Math.ceil(first.total / first.page_size)
    if (pages <= 1) return first.items
    const rest = await Promise.all(
      Array.from({ length: pages - 1 }, (_, index) =>
        this.listTemplateGroups({
          ...query,
          page: index + 2,
          pageSize: first.page_size,
        }),
      ),
    )
    return [first, ...rest].flatMap((page) => page.items)
  },
  async getTemplateGroup(id: string): Promise<TemplateGroupReadDto> {
    const response = await httpClient.get<TemplateGroupReadDto>(
      `${basePath}/template-groups/${id}`,
    )
    return response.data
  },
  async createTemplateGroup(
    data: TemplateGroupCreateDto,
  ): Promise<TemplateGroupReadDto> {
    const response = await httpClient.post<TemplateGroupReadDto>(
      `${basePath}/template-groups`,
      data,
    )
    return response.data
  },
  async updateTemplateGroup(
    id: string,
    data: TemplateGroupUpdateDto,
  ): Promise<TemplateGroupReadDto> {
    const response = await httpClient.patch<TemplateGroupReadDto>(
      `${basePath}/template-groups/${id}`,
      data,
    )
    return response.data
  },
  async deleteTemplateGroup(id: string): Promise<void> {
    await httpClient.delete(`${basePath}/template-groups/${id}`)
  },
  async createPromptTemplate(
    groupId: string,
    data: PromptTemplateCreateDto,
  ): Promise<TemplateGroupReadDto> {
    const response = await httpClient.post<TemplateGroupReadDto>(
      `${basePath}/template-groups/${groupId}/prompt-templates`,
      data,
    )
    return response.data
  },
  async updatePromptTemplate(
    groupId: string,
    templateId: string,
    data: PromptTemplateUpdateDto,
  ): Promise<TemplateGroupReadDto> {
    const response = await httpClient.patch<TemplateGroupReadDto>(
      `${basePath}/template-groups/${groupId}/prompt-templates/${templateId}`,
      data,
    )
    return response.data
  },
  async deletePromptTemplate(
    groupId: string,
    templateId: string,
  ): Promise<void> {
    await httpClient.delete(
      `${basePath}/template-groups/${groupId}/prompt-templates/${templateId}`,
    )
  },
  async duplicatePromptTemplate(
    groupId: string,
    templateId: string,
  ): Promise<TemplateGroupReadDto> {
    const response = await httpClient.post<TemplateGroupReadDto>(
      `${basePath}/template-groups/${groupId}/prompt-templates/${templateId}/duplicate`,
    )
    return response.data
  },
  async reorderPromptTemplates(
    groupId: string,
    outputRole: 'MAIN_IMAGE' | 'DETAIL_IMAGE',
    templateIds: string[],
  ): Promise<TemplateGroupReadDto> {
    const response = await httpClient.put<TemplateGroupReadDto>(
      `${basePath}/template-groups/${groupId}/prompt-templates/reorder`,
      { output_role: outputRole, prompt_template_ids: templateIds },
    )
    return response.data
  },

  async listProductMaterialGroups(
    query: ProductMaterialGroupListQuery,
  ): Promise<ProductMaterialGroupPageDto> {
    const response = await httpClient.get<ProductMaterialGroupPageDto>(
      `${basePath}/product-material-groups`,
      {
        params: {
          ...pageParams(query),
          search: query.search?.trim() || undefined,
          enabled: query.enabled,
        },
      },
    )
    return response.data
  },
  async listAllProductMaterialGroups(
    query: Omit<ProductMaterialGroupListQuery, 'page' | 'pageSize'> = {},
  ): Promise<ProductMaterialGroupPageDto['items']> {
    const first = await this.listProductMaterialGroups({
      ...query,
      page: 1,
      pageSize: 100,
    })
    const pages = Math.ceil(first.total / first.page_size)
    if (pages <= 1) return first.items
    const rest = await Promise.all(
      Array.from({ length: pages - 1 }, (_, index) =>
        this.listProductMaterialGroups({
          ...query,
          page: index + 2,
          pageSize: first.page_size,
        }),
      ),
    )
    return [first, ...rest].flatMap((page) => page.items)
  },
  async getProductMaterialGroup(
    id: string,
  ): Promise<ProductMaterialGroupReadDto> {
    const response = await httpClient.get<ProductMaterialGroupReadDto>(
      `${basePath}/product-material-groups/${id}`,
    )
    return response.data
  },
  async createProductMaterialGroup(
    data: ProductMaterialGroupCreateDto,
  ): Promise<ProductMaterialGroupReadDto> {
    const response = await httpClient.post<ProductMaterialGroupReadDto>(
      `${basePath}/product-material-groups`,
      data,
    )
    return response.data
  },
  async updateProductMaterialGroup(
    id: string,
    data: ProductMaterialGroupUpdateDto,
  ): Promise<ProductMaterialGroupReadDto> {
    const response = await httpClient.patch<ProductMaterialGroupReadDto>(
      `${basePath}/product-material-groups/${id}`,
      data,
    )
    return response.data
  },
  async deleteProductMaterialGroup(id: string): Promise<void> {
    await httpClient.delete(`${basePath}/product-material-groups/${id}`)
  },
  async attachAsset(
    groupId: string,
    assetId: string,
    role: Exclude<MaterialRole, 'AI_OUTPUT'>,
  ): Promise<ProductMaterialGroupReadDto> {
    const response = await httpClient.post<ProductMaterialGroupReadDto>(
      `${basePath}/product-material-groups/${groupId}/assets`,
      { asset_id: assetId, role },
    )
    return response.data
  },
  async detachAsset(groupId: string, assetId: string): Promise<void> {
    await httpClient.delete(
      `${basePath}/product-material-groups/${groupId}/assets/${assetId}`,
    )
  },
  async replaceTemplateBindings(
    groupId: string,
    mode: GenerationMode,
    templateGroupIds: string[],
  ): Promise<ProductMaterialGroupReadDto> {
    const response = await httpClient.put<ProductMaterialGroupReadDto>(
      `${basePath}/product-material-groups/${groupId}/template-bindings/${mode}`,
      { template_group_ids: templateGroupIds },
    )
    return response.data
  },

  async submitGeneration(
    data: InstantGenerationSubmitDto | BatchGenerationSubmitDto,
  ): Promise<GenerationJobReadDto> {
    const response = await httpClient.post<GenerationJobReadDto>(
      `${basePath}/generation-jobs`,
      data,
    )
    return response.data
  },
  async listGenerationJobs(
    query: GenerationJobListQuery,
  ): Promise<GenerationJobPageDto> {
    const response = await httpClient.get<GenerationJobPageDto>(
      `${basePath}/generation-jobs`,
      {
        params: {
          ...pageParams(query),
          work_mode: query.workMode,
          mode: query.mode,
          status: query.status,
        },
      },
    )
    return response.data
  },
  async getGenerationJob(id: string): Promise<GenerationJobReadDto> {
    const response = await httpClient.get<GenerationJobReadDto>(
      `${basePath}/generation-jobs/${id}`,
    )
    return response.data
  },
  async retryGenerationItems(
    id: string,
    data: GenerationRetryRequestDto,
  ): Promise<GenerationJobReadDto> {
    const response = await httpClient.post<GenerationJobReadDto>(
      `${basePath}/generation-jobs/${id}/retry-failed-items`,
      data,
    )
    return response.data
  },
}
