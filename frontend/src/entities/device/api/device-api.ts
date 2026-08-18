import { httpClient, type PageDto, type PageParams } from '@/shared/api'

import type {
  DeviceCreateDto,
  DeviceProviderInventoryReadDto,
  DeviceReadDto,
  DeviceUpdateDto,
} from './contracts'

export const deviceApi = {
  async list(params: PageParams): Promise<PageDto<DeviceReadDto>> {
    const response = await httpClient.get<PageDto<DeviceReadDto>>(
      '/api/v1/devices',
      {
        params: { page: params.page, page_size: params.pageSize },
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

  async getProviderInventories(
    deviceId: string,
  ): Promise<DeviceProviderInventoryReadDto[]> {
    const response = await httpClient.get<DeviceProviderInventoryReadDto[]>(
      `/api/v1/devices/${deviceId}/provider-inventories`,
    )
    return response.data
  },
}
