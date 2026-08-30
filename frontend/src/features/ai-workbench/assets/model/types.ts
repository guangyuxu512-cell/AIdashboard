export type MaterialRole = 'PRODUCT_SOURCE' | 'STYLE_REFERENCE' | 'AI_OUTPUT'

export type MaterialAssetSourceType =
  'LOCAL_UPLOAD' | 'MATERIAL_IMPORT' | 'AI_GENERATION'

export type GenerationMode = 'NORMAL_GENERATION' | 'STYLE_REPLICATION'

export interface MaterialAssetReference {
  assetId: string
  name: string
  mediaType: string
  sourceType: MaterialAssetSourceType
  role: MaterialRole
  previewUrl: string
  width?: number
  height?: number
  sizeBytes?: number
  generationMode?: GenerationMode
  objectUrl?: boolean
}

export interface ProductMaterialGroup {
  id: string
  name: string
  sku?: string
  enabled: boolean
  normalGenerationEnabled: boolean
  styleReplicationEnabled: boolean
  defaultTemplateGroupId: string | null
  createdAt: string
  updatedAt: string
  assets: MaterialAssetReference[]
}

export interface ProductMaterialGroupInput {
  name: string
  sku?: string
}

export interface TemplateGroupOption {
  id: string
  label: string
  modes: readonly GenerationMode[]
}

export type ProductMaterialFilter = 'all' | 'enabled' | 'disabled'

export const MATERIAL_ROLE_META: Record<MaterialRole, { label: string }> = {
  PRODUCT_SOURCE: { label: '商品素材' },
  STYLE_REFERENCE: { label: '复刻参考' },
  AI_OUTPUT: { label: 'AI成品' },
}

export const TEMPLATE_GROUP_OPTIONS: readonly TemplateGroupOption[] = [
  {
    id: 'tg-standard-a',
    label: '电商标准套图 A',
    modes: ['NORMAL_GENERATION', 'STYLE_REPLICATION'],
  },
  {
    id: 'tg-minimal-main',
    label: '极简主图组',
    modes: ['NORMAL_GENERATION'],
  },
  {
    id: 'tg-lifestyle',
    label: '生活场景组',
    modes: ['NORMAL_GENERATION', 'STYLE_REPLICATION'],
  },
  {
    id: 'tg-new-product-detail',
    label: '新品详情套图',
    modes: ['NORMAL_GENERATION'],
  },
] as const

export const UNBOUND_TEMPLATE_GROUP_VALUE = '__unbound__'
