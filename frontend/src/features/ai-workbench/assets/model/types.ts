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
  enabled: boolean
  normalGenerationEnabled: boolean
  styleReplicationEnabled: boolean
  normalTemplateGroupIds: string[]
  styleReplicationTemplateGroupIds: string[]
  createdAt: string
  updatedAt: string
  assets: MaterialAssetReference[]
}

export interface ProductMaterialGroupInput {
  name: string
}

export interface TemplateGroupOption {
  id: string
  label: string
  mode: GenerationMode
}

export type ProductMaterialFilter = 'all' | 'enabled' | 'disabled'

export const MATERIAL_ROLE_META: Record<MaterialRole, { label: string }> = {
  PRODUCT_SOURCE: { label: '商品素材' },
  STYLE_REFERENCE: { label: '复刻参考' },
  AI_OUTPUT: { label: 'AI成品' },
}

export const TEMPLATE_GROUP_OPTIONS: readonly TemplateGroupOption[] = [
  {
    id: 'normal-standard-set',
    label: '电商标准套图 A',
    mode: 'NORMAL_GENERATION',
  },
  {
    id: 'normal-minimal-main',
    label: '极简主图组',
    mode: 'NORMAL_GENERATION',
  },
  {
    id: 'normal-lifestyle-set',
    label: '生活场景套图',
    mode: 'NORMAL_GENERATION',
  },
  {
    id: 'normal-new-product-detail',
    label: '新品详情套图',
    mode: 'NORMAL_GENERATION',
  },
  {
    id: 'style-competitor-a',
    label: '竞品复刻 A',
    mode: 'STYLE_REPLICATION',
  },
  {
    id: 'style-minimal-replication',
    label: '极简风格复刻',
    mode: 'STYLE_REPLICATION',
  },
  {
    id: 'style-scene-replication',
    label: '场景复刻组',
    mode: 'STYLE_REPLICATION',
  },
] as const
