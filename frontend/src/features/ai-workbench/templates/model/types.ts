import {
  GENERATION_OUTPUT_FORMAT_META,
  GENERATION_SIZE_OPTIONS,
  type GenerationConfig,
  type GenerationOutputFormat,
  type GenerationSize,
} from '../../shared/model/generation-config'
import {
  GENERATION_MODE_META,
  type GenerationMode,
} from '../../shared/model/generation-mode'
import {
  GENERATION_OUTPUT_ROLE_META,
  type GenerationOutputRole,
} from '../../shared/model/generation-output'

export { GENERATION_MODE_META }
export type { GenerationMode }

export type TemplateOutputRole = GenerationOutputRole

export type TemplateRoleFilter = 'ALL' | TemplateOutputRole

export type TemplateOutputFormat = GenerationOutputFormat

export const TEMPLATE_SIZE_OPTIONS = GENERATION_SIZE_OPTIONS

export type TemplateSize = GenerationSize

export interface PromptTemplate extends GenerationConfig {
  id: string
  name: string
  enabled: boolean
  outputRole: TemplateOutputRole
  variables: string[]
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

export const TEMPLATE_OUTPUT_ROLE_META = GENERATION_OUTPUT_ROLE_META

export const TEMPLATE_OUTPUT_FORMAT_META = GENERATION_OUTPUT_FORMAT_META
