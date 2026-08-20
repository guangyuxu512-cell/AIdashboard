import { describe, expect, it, vi } from 'vitest'

import type { DeviceOfficeAssetManifest } from './device-office-assets'
import {
  ART_ASSETS_PENDING,
  loadDeviceOfficeAssetManifest,
  ManifestActorAssetProvider,
  REFERENCE_PREVIEW_MODE,
} from './device-office-assets'

const pendingManifest: DeviceOfficeAssetManifest = {
  version: 2,
  status: ART_ASSETS_PENDING,
  designCanvas: { width: 1440, height: 810 },
  scene: {
    light: { background: null, backEnvironment: null, foreground: null },
    dark: { background: null, backEnvironment: null, foreground: null },
  },
  actors: {
    idle: null,
    work: null,
    sleep: null,
    error: null,
    coffee: null,
    walk: null,
    celebrate: null,
  },
  screens: {
    empty: null,
    onlineIdle: null,
    busy: null,
    offline: null,
    error: null,
  },
  referencePreview: {
    light: null,
    dark: { format: 'image', src: '/reference.png' },
  },
}

describe('device office formal asset contract', () => {
  it('keeps actor format and accent independent from device business state', () => {
    const provider = new ManifestActorAssetProvider(pendingManifest)
    expect(
      provider.resolve({ actorState: 'idle', accentVariant: 'blue' }),
    ).toBeNull()
    expect(REFERENCE_PREVIEW_MODE).toBe('REFERENCE_PREVIEW')
  })

  it('loads a valid fixed-canvas manifest and rejects invalid input', async () => {
    const validFetcher = vi.fn(
      async () =>
        new Response(JSON.stringify(pendingManifest), { status: 200 }),
    ) as unknown as typeof fetch
    expect((await loadDeviceOfficeAssetManifest(validFetcher)).status).toBe(
      ART_ASSETS_PENDING,
    )

    const invalidFetcher = vi.fn(
      async () => new Response(JSON.stringify({ version: 1 }), { status: 200 }),
    ) as unknown as typeof fetch
    await expect(loadDeviceOfficeAssetManifest(invalidFetcher)).rejects.toThrow(
      'manifest is invalid',
    )
  })
})
