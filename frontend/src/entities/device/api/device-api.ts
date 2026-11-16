import { httpClient, type PageDto, type PageParams } from '@/shared/api'

import type {
  DeviceCreateDto,
  DeviceLocalShopInventoryDto,
  DeviceReadDto,
  DeviceSkillCapabilityReadDto,
  DeviceUpdateDto,
  WorkerCredentialReadDto,
  WorkerTokenIssuedReadDto,
} from './contracts'

export const deviceApi = {
  async list(
    params: PageParams & { search?: string },
  ): Promise<PageDto<DeviceReadDto>> {
    const response = await httpClient.get<PageDto<DeviceReadDto>>(
      '/api/v1/devices',
      {
        params: {
          page: params.page,
          page_size: params.pageSize,
          ...(params.search?.trim() ? { q: params.search.trim() } : {}),
        },
      },
    )
    return response.data
  },

  async get(deviceId: string): Promise<DeviceReadDto> {
    const response = await httpClient.get<DeviceReadDto>(
      `/api/v1/devices/${deviceId}`,
    )
    return response.data
  },

  async getLocalShops(deviceId: string): Promise<DeviceLocalShopInventoryDto> {
    const response = await httpClient.get<DeviceLocalShopInventoryDto>(
      `/api/v1/devices/${deviceId}/local-shops`,
    )
    return response.data
  },

  async create(data: DeviceCreateDto): Promise<DeviceReadDto> {
    const response = await httpClient.post<DeviceReadDto>(
      '/api/v1/devices',
      data,
    )
    return response.data
  },

  async update(
    deviceId: string,
    data: DeviceUpdateDto,
  ): Promise<DeviceReadDto> {
    const response = await httpClient.patch<DeviceReadDto>(
      `/api/v1/devices/${deviceId}`,
      data,
    )
    return response.data
  },

  async remove(deviceId: string): Promise<void> {
    await httpClient.delete(`/api/v1/devices/${deviceId}`)
  },

  async getSkillCapabilities(
    deviceId: string,
  ): Promise<DeviceSkillCapabilityReadDto[]> {
    const response = await httpClient.get<DeviceSkillCapabilityReadDto[]>(
      `/api/v1/devices/${deviceId}/skill-capabilities`,
    )
    return response.data
  },

  async getWorkerCredential(
    deviceId: string,
  ): Promise<WorkerCredentialReadDto> {
    const response = await httpClient.get<WorkerCredentialReadDto>(
      `/api/v1/devices/${deviceId}/worker-credential`,
    )
    return response.data
  },

  async issueWorkerCredential(
    deviceId: string,
  ): Promise<WorkerTokenIssuedReadDto> {
    const response = await httpClient.post<WorkerTokenIssuedReadDto>(
      `/api/v1/devices/${deviceId}/worker-credential/issue`,
    )
    return response.data
  },

  async rotateWorkerCredential(
    deviceId: string,
  ): Promise<WorkerTokenIssuedReadDto> {
    const response = await httpClient.post<WorkerTokenIssuedReadDto>(
      `/api/v1/devices/${deviceId}/worker-credential/rotate`,
    )
    return response.data
  },

  async revokeWorkerCredential(deviceId: string): Promise<void> {
    await httpClient.post(
      `/api/v1/devices/${deviceId}/worker-credential/revoke`,
    )
  },
}
