import type {
  DeviceListItemViewModel,
  DeviceRuntimeStatus,
} from '@/entities/device'

import type {
  DeviceAvatarVariant,
  DeviceVisualState,
  OfficeStationViewModel,
} from './types'

export const OFFICE_PAGE_SIZE = 9

const AVATAR_ACCENTS = [
  '#4a9cff',
  '#42bf82',
  '#8a63e6',
  '#f09a3e',
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

export function getAvatarVariant(deviceId: string): DeviceAvatarVariant {
  const hash = hashStableId(deviceId)
  const index = hash % AVATAR_ACCENTS.length
  return {
    index,
    accentColor: AVATAR_ACCENTS[index]!,
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
      avatarVariant: device ? getAvatarVariant(device.deviceId) : null,
    }
  })
}
