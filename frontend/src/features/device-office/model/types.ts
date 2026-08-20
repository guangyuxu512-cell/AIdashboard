import type { DeviceListItemViewModel } from '@/entities/device'

export type DeviceVisualState =
  'empty' | 'onlineIdle' | 'busy' | 'offline' | 'error'

export type DeviceCenterViewMode = 'office' | 'list'

export type DeviceActorState =
  'idle' | 'work' | 'sleep' | 'error' | 'coffee' | 'walk' | 'celebrate'

export type DeviceAccentVariant = 'blue' | 'green' | 'purple' | 'orange'

export interface DeviceActorVariant {
  accentVariant: DeviceAccentVariant
  accessory: 'scarf' | 'badge' | 'antenna'
}

export interface OfficeStationViewModel {
  slot: number
  device: DeviceListItemViewModel | null
  visualState: DeviceVisualState
  actorState: DeviceActorState | null
  actorVariant: DeviceActorVariant | null
}
