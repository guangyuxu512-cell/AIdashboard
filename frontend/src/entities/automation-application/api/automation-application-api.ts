import { httpClient } from '@/shared/api'

import type {
  AutomationApplicationConfigDto,
  AutomationApplicationConfigUpsertDto,
} from './contracts'

export const automationApplicationApi = {
  async get(appId: string): Promise<AutomationApplicationConfigDto | null> {
    const response = await httpClient.get<AutomationApplicationConfigDto | null>(
      `/api/v1/automation-app-configs/yingdao/${encodeURIComponent(appId)}`,
    )
    return response.data
  },

  async upsert(
    appId: string,
    data: AutomationApplicationConfigUpsertDto,
  ): Promise<AutomationApplicationConfigDto> {
    const response = await httpClient.put<AutomationApplicationConfigDto>(
      `/api/v1/automation-app-configs/yingdao/${encodeURIComponent(appId)}`,
      data,
    )
    return response.data
  },
}
