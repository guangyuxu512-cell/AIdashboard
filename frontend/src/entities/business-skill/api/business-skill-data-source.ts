import { apiMode } from '@/shared/api'

import type { BusinessSkillCatalogItemViewModel } from '../model/types'
import { getBusinessSkillCatalog } from './business-skill-api'
import { mapBusinessSkillCatalogItem } from './business-skill-mapper'

export async function loadBusinessSkillCatalog(
  deviceId: string,
): Promise<BusinessSkillCatalogItemViewModel[]> {
  if (apiMode === 'mock') return []
  const rows = await getBusinessSkillCatalog(deviceId)
  return rows.map(mapBusinessSkillCatalogItem)
}
