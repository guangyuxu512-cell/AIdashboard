export type AiModelCapability = 'NORMAL_GENERATION' | 'STYLE_REPLICATION'
export type AiModelSize = '1:1' | '3:4' | '4:3' | '16:9'
export type AiModelResolution = '1k' | '2k' | '4k'
export type AiModelProviderCode = 'toapis'

export interface AiModelViewModel {
  modelId: string
  displayName: string
  modelCode: string
  providerCode: AiModelProviderCode
  enabled: boolean
  isDefault: boolean
  capabilities: AiModelCapability[]
  maxInputImages: number
  supportedSizes: AiModelSize[]
  supportedResolutions: AiModelResolution[]
  createdAt: string
  updatedAt: string
}

export interface AiModelCreateInput {
  displayName: string
  modelCode: string
  providerCode: AiModelProviderCode
  enabled: boolean
  isDefault: boolean
  capabilities: AiModelCapability[]
  maxInputImages: number
  supportedSizes: AiModelSize[]
  supportedResolutions: AiModelResolution[]
}

export interface AiModelUpdateInput {
  displayName: string
  enabled: boolean
  isDefault: boolean
  capabilities: AiModelCapability[]
  maxInputImages: number
  supportedSizes: AiModelSize[]
  supportedResolutions: AiModelResolution[]
}

export const AI_MODEL_CAPABILITY_OPTIONS = [
  { label: '普通生图', value: 'NORMAL_GENERATION' },
  { label: '风格复刻', value: 'STYLE_REPLICATION' },
] as const

export const AI_MODEL_SIZE_OPTIONS = [
  { label: '1:1', value: '1:1' },
  { label: '3:4', value: '3:4' },
  { label: '4:3', value: '4:3' },
  { label: '16:9', value: '16:9' },
] as const

export const AI_MODEL_RESOLUTION_OPTIONS = [
  { label: '1K', value: '1k' },
  { label: '2K', value: '2k' },
  { label: '4K', value: '4k' },
] as const

export const AI_MODEL_PROVIDER_OPTIONS = [
  { label: 'ToAPIs', value: 'toapis' },
] as const

export function getAiModelCapabilityLabel(
  capability: AiModelCapability,
): string {
  return (
    AI_MODEL_CAPABILITY_OPTIONS.find((item) => item.value === capability)
      ?.label ?? capability
  )
}
