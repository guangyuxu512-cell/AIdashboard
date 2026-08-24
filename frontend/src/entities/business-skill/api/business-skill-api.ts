import { httpClient } from '@/shared/api'

import type { BusinessSkillCatalogItemReadDto } from './contracts'

export async function getBusinessSkillCatalog(
  deviceId: string,
): Promise<BusinessSkillCatalogItemReadDto[]> {
  const response = await httpClient.get<BusinessSkillCatalogItemReadDto[]>(
    `/api/v1/devices/${deviceId}/business-skills`,
  )
  return response.data
}
