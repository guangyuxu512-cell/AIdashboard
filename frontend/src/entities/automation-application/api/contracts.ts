export type AutomationInputTypeDto = 'text' | 'number' | 'boolean' | 'select'

export interface AutomationInputFieldDto {
  name: string
  label: string
  type: AutomationInputTypeDto
  required: boolean
  default_value: unknown
  options: string[]
}

export interface AutomationInputSchemaDto {
  fields: AutomationInputFieldDto[]
}

export interface AutomationApplicationConfigDto {
  config_id: string
  provider_code: 'yingdao'
  app_id: string
  schema_source: 'manual' | 'provider'
  input_schema: AutomationInputSchemaDto
  default_values: Record<string, unknown>
  version: number
  created_at: string
  updated_at: string
}

export interface AutomationApplicationConfigUpsertDto {
  input_schema: AutomationInputSchemaDto
}

export interface AutomationParameterPresetDto {
  preset_id: string
  team_id: string
  created_by_user_id: string
  app_id: string
  name: string
  common_parameters: Record<string, unknown>
  shop_overrides: Record<string, Record<string, unknown>>
  created_at: string
  updated_at: string
}

export interface AutomationParameterPresetSaveDto {
  name: string
  common_parameters: Record<string, unknown>
  shop_overrides: Record<string, Record<string, unknown>>
}
