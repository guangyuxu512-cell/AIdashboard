import type { DeviceListItemViewModel } from '@/entities/device'

export type DeviceVisualState =
  | 'empty'
  | 'onlineIdle'
  | 'busy'
  | 'offline'
  | 'error'

export type DeviceCenterViewMode = 'office' | 'list'

export interface DeviceMascotVariant {
  index: number
  bodyColor: string
  accentColor: string
  accessory: 'scarf' | 'badge' | 'antenna'
}

export interface OfficeStationViewModel {
  slot: number
  device: DeviceListItemViewModel | null
  visualState: DeviceVisualState
  mascotVariant: DeviceMascotVariant | null
}
