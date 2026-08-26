import type { PageDto } from '@/shared/api'
import { apiClient } from '@/shared/api'

import type { DeviceListRequest, DeviceReadDto } from './contracts'

export async function getDevices(
  params: DeviceListRequest,
): Promise<PageDto<DeviceReadDto>> {
  const response = await apiClient.get<PageDto<DeviceReadDto>>('devices', {
    params,
  })
  return response.data
}

export async function getDevice(deviceId: string): Promise<DeviceReadDto> {
  const response = await apiClient.get<DeviceReadDto>(
    `devices/${encodeURIComponent(deviceId)}`,
  )
  return response.data
}
