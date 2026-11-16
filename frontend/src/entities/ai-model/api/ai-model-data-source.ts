import { apiMode, type ApiMode } from '@/shared/api'

import type {
  AiModelCreateInput,
  AiModelUpdateInput,
  AiModelViewModel,
} from '../model/types'
import { aiModelApi } from './ai-model-api'
import type {
  AiModelCreateDto,
  AiModelReadDto,
  AiModelUpdateDto,
} from './contracts'

export interface AiModelDataSource {
  readonly mode: ApiMode
  list(): Promise<AiModelViewModel[]>
  get(modelId: string): Promise<AiModelViewModel>
  create(input: AiModelCreateInput): Promise<AiModelViewModel>
  update(modelId: string, input: AiModelUpdateInput): Promise<AiModelViewModel>
  setDefault(modelId: string): Promise<AiModelViewModel>
}

function mapModel(dto: AiModelReadDto): AiModelViewModel {
  return {
    modelId: dto.model_id,
    displayName: dto.display_name,
    modelCode: dto.model_code,
    providerCode: dto.provider_code,
    enabled: dto.enabled,
    isDefault: dto.is_default,
    capabilities: [...dto.capabilities],
    maxInputImages: dto.max_input_images,
    supportedSizes: [...dto.supported_sizes],
    supportedResolutions: [...dto.supported_resolutions],
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  }
}

function mapCreate(input: AiModelCreateInput): AiModelCreateDto {
  return {
    display_name: input.displayName.trim(),
    model_code: input.modelCode.trim(),
    provider_code: input.providerCode,
    enabled: input.enabled,
    is_default: input.isDefault,
    capabilities: [...input.capabilities],
    max_input_images: input.maxInputImages,
    supported_sizes: [...input.supportedSizes],
    supported_resolutions: [...input.supportedResolutions],
  }
}

function mapUpdate(input: AiModelUpdateInput): AiModelUpdateDto {
  return {
    display_name: input.displayName.trim(),
    enabled: input.enabled,
    is_default: input.isDefault,
    capabilities: [...input.capabilities],
    max_input_images: input.maxInputImages,
    supported_sizes: [...input.supportedSizes],
    supported_resolutions: [...input.supportedResolutions],
  }
}

function cloneModel(model: AiModelViewModel): AiModelViewModel {
  return {
    ...model,
    capabilities: [...model.capabilities],
    supportedSizes: [...model.supportedSizes],
    supportedResolutions: [...model.supportedResolutions],
  }
}

function createMockDataSource(): AiModelDataSource {
  const now = new Date().toISOString()
  const models: AiModelViewModel[] = [
    {
      modelId: '13b4f558-cd56-4f11-99fc-c64275e14031',
      displayName: 'GPT Image 2',
      modelCode: 'gpt-image-2',
      providerCode: 'toapis',
      enabled: true,
      isDefault: true,
      capabilities: ['NORMAL_GENERATION', 'STYLE_REPLICATION'],
      maxInputImages: 6,
      supportedSizes: ['1:1', '3:4', '4:3', '16:9'],
      supportedResolutions: ['1k', '2k', '4k'],
      createdAt: now,
      updatedAt: now,
    },
  ]
  let sequence = 1

  const find = (modelId: string): AiModelViewModel => {
    const model = models.find((item) => item.modelId === modelId)
    if (!model) throw new Error('AI模型不存在')
    return model
  }

  return {
    mode: 'mock',
    async list() {
      return models
        .slice()
        .sort(
          (left, right) =>
            Number(right.isDefault) - Number(left.isDefault) ||
            left.displayName.localeCompare(right.displayName),
        )
        .map(cloneModel)
    },
    async get(modelId) {
      return cloneModel(find(modelId))
    },
    async create(input) {
      if (
        models.some(
          (model) =>
            model.providerCode === input.providerCode &&
            model.modelCode === input.modelCode.trim(),
        )
      ) {
        throw new Error('Provider下已存在相同模型Code')
      }
      if (input.isDefault && !input.enabled) throw new Error('默认模型必须启用')
      if (input.isDefault)
        models.forEach((model) => {
          model.isDefault = false
        })
      const created: AiModelViewModel = {
        ...input,
        displayName: input.displayName.trim(),
        modelCode: input.modelCode.trim(),
        modelId: `mock-ai-model-${sequence++}`,
        capabilities: [...input.capabilities],
        supportedSizes: [...input.supportedSizes],
        supportedResolutions: [...input.supportedResolutions],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      }
      models.push(created)
      return cloneModel(created)
    },
    async update(modelId, input) {
      const model = find(modelId)
      if (model.isDefault && (!input.enabled || !input.isDefault))
        throw new Error('请先设置另一个已启用模型为默认模型')
      if (input.isDefault && !input.enabled) throw new Error('默认模型必须启用')
      if (input.isDefault)
        models.forEach((item) => {
          item.isDefault = item.modelId === modelId
        })
      Object.assign(model, {
        ...input,
        displayName: input.displayName.trim(),
        capabilities: [...input.capabilities],
        supportedSizes: [...input.supportedSizes],
        supportedResolutions: [...input.supportedResolutions],
        updatedAt: new Date().toISOString(),
      })
      return cloneModel(model)
    },
    async setDefault(modelId) {
      const model = find(modelId)
      if (!model.enabled) throw new Error('默认模型必须启用')
      models.forEach((item) => {
        item.isDefault = item.modelId === modelId
      })
      model.updatedAt = new Date().toISOString()
      return cloneModel(model)
    },
  }
}

function createRealDataSource(): AiModelDataSource {
  return {
    mode: 'real',
    async list() {
      return (await aiModelApi.list()).map(mapModel)
    },
    async get(modelId) {
      return mapModel(await aiModelApi.get(modelId))
    },
    async create(input) {
      return mapModel(await aiModelApi.create(mapCreate(input)))
    },
    async update(modelId, input) {
      return mapModel(await aiModelApi.update(modelId, mapUpdate(input)))
    },
    async setDefault(modelId) {
      return mapModel(await aiModelApi.setDefault(modelId))
    },
  }
}

export function createAiModelDataSource(mode: ApiMode): AiModelDataSource {
  return mode === 'real' ? createRealDataSource() : createMockDataSource()
}

export const aiModelDataSource = createAiModelDataSource(apiMode)
