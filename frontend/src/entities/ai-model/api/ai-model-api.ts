import { httpClient } from '@/shared/api'

import type {
  AiModelCreateDto,
  AiModelReadDto,
  AiModelUpdateDto,
} from './contracts'

const basePath = '/api/v1/ai-models'

export const aiModelApi = {
  async list(): Promise<AiModelReadDto[]> {
    const response = await httpClient.get<AiModelReadDto[]>(basePath)
    return response.data
  },
  async get(modelId: string): Promise<AiModelReadDto> {
    const response = await httpClient.get<AiModelReadDto>(
      `${basePath}/${modelId}`,
    )
    return response.data
  },
  async create(data: AiModelCreateDto): Promise<AiModelReadDto> {
    const response = await httpClient.post<AiModelReadDto>(basePath, data)
    return response.data
  },
  async update(
    modelId: string,
    data: AiModelUpdateDto,
  ): Promise<AiModelReadDto> {
    const response = await httpClient.patch<AiModelReadDto>(
      `${basePath}/${modelId}`,
      data,
    )
    return response.data
  },
  async setDefault(modelId: string): Promise<AiModelReadDto> {
    const response = await httpClient.post<AiModelReadDto>(
      `${basePath}/${modelId}/default`,
    )
    return response.data
  },
}
