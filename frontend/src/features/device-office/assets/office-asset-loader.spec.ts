import { describe, expect, it } from 'vitest'

import { OFFICE_ASSET_KEYS, officeAssetManifest } from './office-asset-manifest'
import { checkOfficeAssetAvailability } from './office-asset-loader'

describe('office asset loader boundary', () => {
  it('requires the complete replaceable GLB set', () => {
    expect(OFFICE_ASSET_KEYS).toEqual([
      'mascot',
      'desk',
      'chair',
      'monitor',
      'officeProps',
    ])
    expect(officeAssetManifest.mascot.requiredAnimations).toEqual([
      'Idle',
      'Walk',
      'SitWork',
      'Sleep',
      'CoffeeIdle',
    ])
  })

  it('does not treat an incomplete asset set as renderable', async () => {
    const availability = await checkOfficeAssetAvailability(async (url) =>
      url.endsWith('desk.glb'),
    )
    expect(availability.ready).toBe(false)
    expect(availability.missing.map((asset) => asset.key)).toEqual([
      'mascot',
      'chair',
      'monitor',
      'officeProps',
    ])
  })
})

