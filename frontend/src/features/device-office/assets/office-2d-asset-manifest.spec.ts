import { describe, expect, it } from 'vitest'

import {
  officeActorAssets,
  officeScreenAssets,
  officeThemeLayerAssets,
} from './office-2d-asset-manifest'

describe('device office 2.5D asset manifest', () => {
  it('contains replaceable light, dark, actor and screen layers without GLB assets', () => {
    const urls = [
      ...Object.values(officeThemeLayerAssets).flatMap(Object.values),
      ...Object.values(officeActorAssets),
      ...Object.values(officeScreenAssets),
    ]

    expect(Object.keys(officeActorAssets)).toEqual([
      'empty',
      'onlineIdle',
      'busy',
      'offline',
      'error',
    ])
    expect(urls.every((url) => url.startsWith('/assets/device-office/'))).toBe(true)
    expect(urls.some((url) => url.endsWith('.glb'))).toBe(false)
  })
})
