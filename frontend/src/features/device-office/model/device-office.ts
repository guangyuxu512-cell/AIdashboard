import type {
  DeviceListItemViewModel,
  DeviceRuntimeStatus,
} from '@/entities/device'

import type {
  DeviceMascotVariant,
  DeviceVisualState,
  OfficeStationViewModel,
} from './types'

export const OFFICE_PAGE_SIZE = 9

const MASCOT_PALETTES = [
  ['#7b9fc1', '#d9ad66'],
  ['#d39a6a', '#6b8e9d'],
  ['#9184b6', '#d8a96d'],
  ['#6f9d82', '#d7a86e'],
  ['#b77f88', '#6f91af'],
  ['#7296a1', '#c9907a'],
] as const

const ACCESSORIES = ['scarf', 'badge', 'antenna'] as const

export function hashStableId(value: string): number {
  let hash = 0x811c9dc5
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 0x01000193)
  }
  return hash >>> 0
}

export function getMascotVariant(deviceId: string): DeviceMascotVariant {
  const hash = hashStableId(deviceId)
  const index = hash % MASCOT_PALETTES.length
  const palette = MASCOT_PALETTES[index]!
  return {
    index,
    bodyColor: palette[0],
    accentColor: palette[1],
    accessory: ACCESSORIES[(hash >>> 8) % ACCESSORIES.length]!,
  }
}

export function mapDeviceVisualState(
  runtimeStatus: DeviceRuntimeStatus,
): Exclude<DeviceVisualState, 'empty'> {
  switch (runtimeStatus) {
    case 'online':
      return 'onlineIdle'
    case 'busy':
      return 'busy'
    case 'error':
      return 'error'
    case 'offline':
    case 'unavailable':
      return 'offline'
  }
}

export function createOfficeStations(
  devices: DeviceListItemViewModel[],
): OfficeStationViewModel[] {
  return Array.from({ length: OFFICE_PAGE_SIZE }, (_, index) => {
    const device = devices[index] ?? null
    return {
      slot: index + 1,
      device,
      visualState: device
        ? mapDeviceVisualState(device.runtimeStatus)
        : 'empty',
      mascotVariant: device ? getMascotVariant(device.deviceId) : null,
    }
  })
}
