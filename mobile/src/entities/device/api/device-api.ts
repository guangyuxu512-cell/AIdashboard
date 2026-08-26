import type { PageDto } from '@/shared/api'
import { apiClient } from '@/shared/api'

import type {
  DeviceListRequest,
  DeviceProviderInventoryReadDto,
  DeviceReadDto,
  DeviceSkillCapabilityReadDto,
} from './contracts'

function devicePath(deviceId: string, suffix = ''): string {
  return `devices/${encodeURIComponent(deviceId)}${suffix}`
}

export async function getDevices(
  params: DeviceListRequest,
): Promise<PageDto<DeviceReadDto>> {
  const response = await apiClient.get<PageDto<DeviceReadDto>>('devices', {
    params,
  })
  return response.data
}

export async function getDevice(deviceId: string): Promise<DeviceReadDto> {
  const response = await apiClient.get<DeviceReadDto>(devicePath(deviceId))
  return response.data
}

export async function getDeviceProviderInventories(
  deviceId: string,
): Promise<DeviceProviderInventoryReadDto[]> {
  const response = await apiClient.get<DeviceProviderInventoryReadDto[]>(
    devicePath(deviceId, '/provider-inventories'),
  )
  return response.data
}

export async function getDeviceSkillCapabilities(
  deviceId: string,
): Promise<DeviceSkillCapabilityReadDto[]> {
  const response = await apiClient.get<DeviceSkillCapabilityReadDto[]>(
    devicePath(deviceId, '/skill-capabilities'),
  )
  return response.data
}
