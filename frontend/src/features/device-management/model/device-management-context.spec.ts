import { describe, expect, it, vi } from 'vitest'

import type { YingdaoInventoryViewModel } from '@/entities/device'

import {
  loadDeviceLocalShops,
  loadDeviceInventories,
} from './device-management-context'

const inventory: YingdaoInventoryViewModel = {
  availabilityStatus: 'available',
  providerStatus: 'ready',
  statusReason: null,
  available: true,
  loggedIn: true,
  enterpriseAccount: false,
  providerVersion: '6.3.6',
  executionAvailable: true,
  executionVersion: '6.3.6',
  executionUnavailableReason: null,
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

  it('keeps other devices independent when a local shop inventory fails', async () => {
    const loader = vi.fn(async () => {
      throw new Error('binding query unavailable')
    })

    await expect(
      loadDeviceLocalShops(['device-a', 'device-b'], loader),
    ).resolves.toEqual({
      'device-a': null,
      'device-b': null,
    })
  })

  it('keeps cached auxiliary values when a background refresh fails', async () => {
    const inventoryLoader = vi.fn(async () => {
      throw new Error('provider unavailable')
    })
    const localShopLoader = vi.fn(async () => {
      throw new Error('binding unavailable')
    })
    const cached = { device_id: 'device-a', available: true, last_discovered_at: null, shops: [] }

    await expect(
      loadDeviceInventories(['device-a'], inventoryLoader, {
        'device-a': inventory,
      }),
    ).resolves.toEqual({ 'device-a': inventory })
    await expect(
      loadDeviceLocalShops(['device-a'], localShopLoader, {
        'device-a': cached,
      }),
    ).resolves.toEqual({ 'device-a': cached })
  })
})
