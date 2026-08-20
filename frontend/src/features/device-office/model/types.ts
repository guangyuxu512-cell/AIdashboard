import type { DeviceListItemViewModel } from '@/entities/device'

export type DeviceVisualState =
  | 'empty'
  | 'onlineIdle'
  | 'busy'
  | 'offline'
  | 'error'

export type DeviceCenterViewMode = 'office' | 'list'

export type DeviceLocalBehavior = 'idle' | 'work' | 'sleep' | 'coffee' | 'walk'

export interface DeviceActorVariant {
  index: number
  accentColor: string
  accessory: 'scarf' | 'badge' | 'antenna'
}

export interface OfficeStationViewModel {
  slot: number
  device: DeviceListItemViewModel | null
  visualState: DeviceVisualState
  localBehavior: DeviceLocalBehavior | null
  actorVariant: DeviceActorVariant | null
}
