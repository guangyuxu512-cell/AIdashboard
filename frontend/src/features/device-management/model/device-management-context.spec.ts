import { describe, expect, it, vi } from 'vitest'

import type { YingdaoInventoryViewModel } from '@/entities/device'

import {
  loadDeviceBindingCounts,
  loadDeviceInventories,
} from './device-management-context'

const inventory: YingdaoInventoryViewModel = {
  availabilityStatus: 'available',
  available: true,
  loggedIn: true,
  enterpriseAccount: false,
  providerVersion: '6.3.6',
  accountDisplay: 'GY00999',
  accountType: 'PersonalBasic',
  applicationCount: 8,
  applications: [],
  lastDiscoveredAtDisplay: '刚刚',
}

describe('device management auxiliary context', () => {
  it('keeps successful provider inventories when another device inventory fails', async () => {
    const loader = vi.fn(async (deviceId: string) => {
      if (deviceId === 'device-b') throw new Error('provider unavailable')
      return inventory
    })

    await expect(
      loadDeviceInventories(['device-a', 'device-b'], loader),
    ).resolves.toEqual({
      'device-a': inventory,
      'device-b': null,
    })
  })

  it('falls back binding counts independently when the shop query fails', async () => {
    const loader = vi.fn(async () => {
      throw new Error('binding query unavailable')
    })

    await expect(
      loadDeviceBindingCounts(['device-a', 'device-b'], loader),
    ).resolves.toEqual({
      'device-a': null,
      'device-b': null,
    })
  })
})
