export interface DeviceRuntime {
  deviceId: string
  workerVersion: string
  connectionStatus: 'online' | 'offline'
  lastSeenAt: string
  startedAt: string
  updatedAt: string
}

export interface Device {
  deviceId: string
  displayName: string
  enabled: boolean
  location: string | null
  note: string | null
  deletedAt: string | null
  workerRuntime: DeviceRuntime | null
  createdAt: string
  updatedAt: string
}

export interface DeviceCapabilitySummary {
  business: number
  internal: number
  unclassified: number
  total: number
}
