import { describe, expect, it, vi } from 'vitest'

import { loadDeviceLocalShops } from './device-management-context'

describe('device management auxiliary context', () => {
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
    const localShopLoader = vi.fn(async () => {
      throw new Error('binding unavailable')
    })
    const cached = { device_id: 'device-a', available: true, last_discovered_at: null, shops: [] }

    await expect(
      loadDeviceLocalShops(['device-a'], localShopLoader, {
        'device-a': cached,
      }),
    ).resolves.toEqual({ 'device-a': cached })
  })
})
