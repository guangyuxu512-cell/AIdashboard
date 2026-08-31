export type GenerationMode = 'NORMAL_GENERATION' | 'STYLE_REPLICATION'

export type TemplateOutputRole = 'MAIN_IMAGE' | 'DETAIL_IMAGE'

export type TemplateRoleFilter = 'ALL' | TemplateOutputRole

export type TemplateOutputFormat = 'SINGLE' | 'COLLAGE_2X2'

export const TEMPLATE_SIZE_OPTIONS = ['1:1', '3:4', '4:3', '16:9'] as const

export type TemplateSize = (typeof TEMPLATE_SIZE_OPTIONS)[number]

export interface PromptTemplate {
  id: string
  name: string
  enabled: boolean
  outputRole: TemplateOutputRole
  outputFormat: TemplateOutputFormat
  size: TemplateSize
  count: number
  variables: string[]
  prompt: string
  negativePrompt: string
  sortOrder: number
  createdAt: string
  updatedAt: string
}

export interface TemplateGroup {
  id: string
  name: string
  mode: GenerationMode
  enabled: boolean
  templates: PromptTemplate[]
  createdAt: string
  updatedAt: string
}

export interface TemplateGroupInput {
  name: string
  mode: GenerationMode
}

export type PromptTemplateInput = Omit<
  PromptTemplate,
  'id' | 'outputRole' | 'sortOrder' | 'createdAt' | 'updatedAt'
>

export const GENERATION_MODE_META: Record<GenerationMode, { label: string }> = {
  NORMAL_GENERATION: { label: '普通生图' },
  STYLE_REPLICATION: { label: '风格复刻' },
}

export const TEMPLATE_OUTPUT_ROLE_META: Record<
  TemplateOutputRole,
  { label: string }
> = {
  MAIN_IMAGE: { label: '主图' },
  DETAIL_IMAGE: { label: '详情' },
}

export const TEMPLATE_OUTPUT_FORMAT_META: Record<
  TemplateOutputFormat,
  { label: string }
> = {
  SINGLE: { label: '单图' },
  COLLAGE_2X2: { label: '四宫格' },
}
