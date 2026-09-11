import { httpClient } from '@/shared/api'

import type {
  AutomationApplicationConfigDto,
  AutomationApplicationConfigUpsertDto,
  AutomationParameterPresetListParams,
  AutomationParameterPresetDto,
  AutomationParameterPresetSaveDto,
  AutomationParameterPresetUpdateDto,
  YingdaoApplicationOptionDto,
} from './contracts'

export const automationApplicationApi = {
  async listYingdaoApplications(): Promise<YingdaoApplicationOptionDto[]> {
    const response = await httpClient.get<YingdaoApplicationOptionDto[]>(
      '/api/v1/automation-app-configs/yingdao/applications',
    )
    return response.data
  },

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

  async listPresets(appId: string): Promise<AutomationParameterPresetDto[]> {
    const response = await httpClient.get<AutomationParameterPresetDto[]>(
      `/api/v1/automation-app-configs/yingdao/${encodeURIComponent(appId)}/parameter-presets`,
    )
    return response.data
  },

  async listAllPresets(
    params: AutomationParameterPresetListParams = {},
  ): Promise<AutomationParameterPresetDto[]> {
    const response = await httpClient.get<AutomationParameterPresetDto[]>(
      '/api/v1/automation-parameter-presets',
      {
        params: {
          ...(params.appId ? { app_id: params.appId } : {}),
          ...(params.query?.trim() ? { q: params.query.trim() } : {}),
        },
      },
    )
    return response.data
  },

  async createPreset(
    appId: string,
    data: AutomationParameterPresetSaveDto,
  ): Promise<AutomationParameterPresetDto> {
    const response = await httpClient.post<AutomationParameterPresetDto>(
      `/api/v1/automation-app-configs/yingdao/${encodeURIComponent(appId)}/parameter-presets`,
      data,
    )
    return response.data
  },

  async updatePreset(
    appId: string,
    presetId: string,
    data: AutomationParameterPresetUpdateDto,
  ): Promise<AutomationParameterPresetDto> {
    const response = await httpClient.patch<AutomationParameterPresetDto>(
      `/api/v1/automation-app-configs/yingdao/${encodeURIComponent(appId)}/parameter-presets/${encodeURIComponent(presetId)}`,
      data,
    )
    return response.data
  },

  async copyPreset(
    appId: string,
    presetId: string,
    name: string,
  ): Promise<AutomationParameterPresetDto> {
    const response = await httpClient.post<AutomationParameterPresetDto>(
      `/api/v1/automation-app-configs/yingdao/${encodeURIComponent(appId)}/parameter-presets/${encodeURIComponent(presetId)}/copy`,
      { name },
    )
    return response.data
  },
}
