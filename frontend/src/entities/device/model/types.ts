export type DeviceStatus = 'online' | 'offline' | 'busy' | 'error'

export type DeviceCapability = 'rpa' | 'python' | 'browser' | 'node'

export type DeviceCapabilityAvailability = 'available' | 'unavailable'

export interface DeviceCapabilityViewModel {
  capability: DeviceCapability
  availability: DeviceCapabilityAvailability
}

/**
 * 设备中心第一版的前端展示模型。
 *
 * 心跳、资源、Worker 版本及能力字段只服务本地 Fixture，不是 Worker 或 Backend 契约。
 */
export interface DeviceListItemViewModel {
  deviceId: string
  deviceName: string
  status: DeviceStatus
  location: string
  systemDisplay: string
  workerVersionDisplay: string
  currentTaskName: string | null
  cpuUsageDisplay: string
  memoryUsageDisplay: string
  lastHeartbeatAtDisplay: string
  tags: string[]
  capabilities: DeviceCapabilityViewModel[]
}
