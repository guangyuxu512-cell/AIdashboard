export type DeviceStatus = 'online' | 'offline' | 'busy' | 'error'

export type DeviceRuntimeStatus = DeviceStatus | 'unavailable'

export type DeviceEnabledStatus = 'enabled' | 'disabled'

export type DeviceCapability = 'rpa' | 'python' | 'browser' | 'node'

export type DeviceCapabilityAvailability = 'available' | 'unavailable'

export type YingdaoAvailabilityStatus =
  | 'available'
  | 'unavailable'
  | 'not_detected'

export interface DeviceCapabilityViewModel {
  capability: DeviceCapability
  availability: DeviceCapabilityAvailability
}

/**
 * 设备中心第一版的前端展示模型。
 *
 * Real API 只提供 Worker 在线状态、版本与最近心跳；资源、当前任务及能力仍只服务 Fixture。
 */
export interface DeviceListItemViewModel {
  deviceId: string
  deviceName: string
  enabled: boolean
  enabledStatus: DeviceEnabledStatus
  runtimeStatus: DeviceRuntimeStatus
  location: string
  note: string
  systemDisplay: string
  workerVersionDisplay: string
  currentTaskName: string | null
  cpuUsageDisplay: string
  memoryUsageDisplay: string
  lastHeartbeatAtDisplay: string
  tags: string[]
  capabilities: DeviceCapabilityViewModel[]
  updatedAtDisplay: string
  dataSource: 'mock' | 'real'
}

export interface DeviceListFilters {
  status: DeviceStatus | null
  tag: string | null
  workerVersion: string | null
  capability: DeviceCapability | null
  keyword: string
}

export interface DeviceSaveInput {
  deviceName: string
  enabled: boolean
  location: string
  note: string
}

export interface ProviderApplicationViewModel {
  appId: string
  appName: string
  packageVersion: string
  entrypoint: string
}

export interface YingdaoInventoryViewModel {
  available: boolean
  availabilityStatus: Exclude<YingdaoAvailabilityStatus, 'not_detected'>
  providerVersion: string
  loggedIn: boolean
  accountDisplay: string
  accountType: string
  enterpriseAccount: boolean
  applicationCount: number
  applications: ProviderApplicationViewModel[]
  lastDiscoveredAtDisplay: string
}
