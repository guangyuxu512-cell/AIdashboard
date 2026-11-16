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

export interface DeviceDataSource {
  getDevices(params: DeviceListRequest): Promise<PageDto<DeviceReadDto>>
  getDevice(deviceId: string): Promise<DeviceReadDto>
  getDeviceProviderInventories(
    deviceId: string,
  ): Promise<DeviceProviderInventoryReadDto[]>
  getDeviceSkillCapabilities(
    deviceId: string,
  ): Promise<DeviceSkillCapabilityReadDto[]>
}

const realDeviceDataSource: DeviceDataSource = {
  async getDevices(params) {
    const response = await apiClient.get<PageDto<DeviceReadDto>>('devices', {
      params,
    })
    return response.data
  },
  async getDevice(deviceId) {
    const response = await apiClient.get<DeviceReadDto>(devicePath(deviceId))
    return response.data
  },
  async getDeviceProviderInventories(deviceId) {
    const response = await apiClient.get<DeviceProviderInventoryReadDto[]>(
      devicePath(deviceId, '/provider-inventories'),
    )
    return response.data
  },
  async getDeviceSkillCapabilities(deviceId) {
    const response = await apiClient.get<DeviceSkillCapabilityReadDto[]>(
      devicePath(deviceId, '/skill-capabilities'),
    )
    return response.data
  },
}

let deviceDataSource = realDeviceDataSource

export function configureDeviceDataSource(dataSource: DeviceDataSource): void {
  deviceDataSource = dataSource
}

export function resetDeviceDataSource(): void {
  deviceDataSource = realDeviceDataSource
}

export function getDevices(
  params: DeviceListRequest,
): Promise<PageDto<DeviceReadDto>> {
  return deviceDataSource.getDevices(params)
}

export function getDevice(deviceId: string): Promise<DeviceReadDto> {
  return deviceDataSource.getDevice(deviceId)
}

export function getDeviceProviderInventories(
  deviceId: string,
): Promise<DeviceProviderInventoryReadDto[]> {
  return deviceDataSource.getDeviceProviderInventories(deviceId)
}

export function getDeviceSkillCapabilities(
  deviceId: string,
): Promise<DeviceSkillCapabilityReadDto[]> {
  return deviceDataSource.getDeviceSkillCapabilities(deviceId)
}
