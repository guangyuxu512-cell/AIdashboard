import type { DeviceCapability, DeviceStatus } from '@/entities/device'

export interface DeviceFilterViewModel {
  status: DeviceStatus | null
  tag: string | null
  workerVersion: string | null
  capability: DeviceCapability | null
  keyword: string
}

export interface DeviceFormViewModel {
  deviceName: string
  enabled: boolean
  location: string
  note: string
}

export type DeviceFormMode = 'create' | 'edit'
