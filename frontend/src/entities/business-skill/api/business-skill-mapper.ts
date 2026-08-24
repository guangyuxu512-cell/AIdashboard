import type { BusinessSkillCatalogItemViewModel } from '../model/types'
import { parseBusinessSkillInputSchema } from '../model/schema-parser'
import type { BusinessSkillCatalogItemReadDto } from './contracts'

export function mapBusinessSkillCatalogItem(
  dto: BusinessSkillCatalogItemReadDto,
): BusinessSkillCatalogItemViewModel {
  if (dto.availability !== 'available' || dto.input_schema === null) {
    return {
      deviceId: dto.device_id,
      skillId: dto.skill_id,
      displayName: dto.display_name,
      version: dto.version,
      availability: dto.availability,
      unavailableReason: dto.unavailable_reason,
      inputSchema: dto.input_schema,
      parameterFields: [],
      configurable: false,
    }
  }
  const parsed = parseBusinessSkillInputSchema(dto.input_schema)
  return {
    deviceId: dto.device_id,
    skillId: dto.skill_id,
    displayName: dto.display_name,
    version: dto.version,
    availability: parsed.supported ? 'available' : 'schema_unsupported',
    unavailableReason: parsed.supported ? null : parsed.reason,
    inputSchema: dto.input_schema,
    parameterFields: parsed.supported ? parsed.fields : [],
    configurable: parsed.supported,
  }
}
