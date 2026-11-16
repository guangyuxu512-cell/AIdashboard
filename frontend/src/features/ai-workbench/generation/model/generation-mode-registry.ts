import {
  GENERATION_MODE_META,
  GENERATION_MODE_ORDER,
  type GenerationMode,
} from '../../shared/model/generation-mode'

export { GENERATION_MODE_ORDER }
export type { GenerationMode }

export type GenerationSourceRole = 'PRODUCT_SOURCE' | 'STYLE_REFERENCE'

export type GenerationInputSlotKey = 'PRODUCT_IMAGES' | 'REFERENCE_IMAGES'

export interface GenerationInputSlotDefinition {
  key: GenerationInputSlotKey
  label: string
  required: boolean
  acceptedMaterialRole: GenerationSourceRole
  allowLocalUpload: boolean
  allowMaterialLibrary: boolean
}

export interface GenerationModeDefinition {
  value: GenerationMode
  label: string
  inputSlots: readonly GenerationInputSlotDefinition[]
  supportsTemplate: boolean
}

const PRODUCT_IMAGES_SLOT: GenerationInputSlotDefinition = {
  key: 'PRODUCT_IMAGES',
  label: '商品图片',
  required: true,
  acceptedMaterialRole: 'PRODUCT_SOURCE',
  allowLocalUpload: true,
  allowMaterialLibrary: true,
}

const REFERENCE_IMAGES_SLOT: GenerationInputSlotDefinition = {
  key: 'REFERENCE_IMAGES',
  label: '参考图片',
  required: true,
  acceptedMaterialRole: 'STYLE_REFERENCE',
  allowLocalUpload: true,
  allowMaterialLibrary: true,
}

export const GENERATION_MODE_REGISTRY: Record<
  GenerationMode,
  GenerationModeDefinition
> = {
  NORMAL_GENERATION: {
    value: 'NORMAL_GENERATION',
    label: GENERATION_MODE_META.NORMAL_GENERATION.label,
    inputSlots: [PRODUCT_IMAGES_SLOT],
    supportsTemplate: true,
  },
  STYLE_REPLICATION: {
    value: 'STYLE_REPLICATION',
    label: GENERATION_MODE_META.STYLE_REPLICATION.label,
    inputSlots: [PRODUCT_IMAGES_SLOT, REFERENCE_IMAGES_SLOT],
    supportsTemplate: true,
  },
}

export function getGenerationModeDefinition(
  mode: GenerationMode,
): GenerationModeDefinition {
  return GENERATION_MODE_REGISTRY[mode]
}
