import type { SchemaParameterField } from '@/shared/types/schema-parameter'

import type { BusinessSkillAvailabilityDto } from '../api/contracts'

export interface BusinessSkillCatalogItemViewModel {
  deviceId: string
  skillId: string
  displayName: string
  version: string
  availability: BusinessSkillAvailabilityDto
  unavailableReason: string | null
  inputSchema: Record<string, unknown> | null
  parameterFields: SchemaParameterField[]
  configurable: boolean
}
