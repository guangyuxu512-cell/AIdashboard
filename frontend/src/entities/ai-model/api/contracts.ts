import type {
  AiModelCapability,
  AiModelProviderCode,
  AiModelResolution,
  AiModelSize,
} from '../model/types'

export interface AiModelReadDto {
  model_id: string
  display_name: string
  model_code: string
  provider_code: AiModelProviderCode
  enabled: boolean
  is_default: boolean
  capabilities: AiModelCapability[]
  max_input_images: number
  supported_sizes: AiModelSize[]
  supported_resolutions: AiModelResolution[]
  created_at: string
  updated_at: string
}

export interface AiModelCreateDto {
  display_name: string
  model_code: string
  provider_code: AiModelProviderCode
  enabled: boolean
  is_default: boolean
  capabilities: AiModelCapability[]
  max_input_images: number
  supported_sizes: AiModelSize[]
  supported_resolutions: AiModelResolution[]
}

export interface AiModelUpdateDto {
  display_name: string
  enabled: boolean
  is_default: boolean
  capabilities: AiModelCapability[]
  max_input_images: number
  supported_sizes: AiModelSize[]
  supported_resolutions: AiModelResolution[]
}
