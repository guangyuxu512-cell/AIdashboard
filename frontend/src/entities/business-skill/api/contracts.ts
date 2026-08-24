export type BusinessSkillAvailabilityDto =
  | 'available'
  | 'schema_unavailable'
  | 'schema_unsupported'

export interface BusinessSkillCatalogItemReadDto {
  device_id: string
  skill_id: string
  display_name: string
  runtime: 'python'
  provider: null
  version: string
  classification: 'business'
  input_schema: Record<string, unknown> | null
  availability: BusinessSkillAvailabilityDto
  unavailable_reason: string | null
  updated_at: string
}
