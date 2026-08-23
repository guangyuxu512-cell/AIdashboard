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
