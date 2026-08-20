import { describe, expect, it, vi } from 'vitest'

import type { DeviceOfficeAssetManifest } from './device-office-assets'
import {
  createDeviceOfficeAssetBundle,
  DEVICE_OFFICE_MANIFEST_URL,
  loadDeviceOfficeAssetManifest,
  ManifestActorAssetProvider,
  preloadDeviceOfficeTheme,
} from './device-office-assets'

const assetManifest: DeviceOfficeAssetManifest = {
  name: 'Device Center Marvis-style 2.5D Assets',
  version: '2.0',
  design_canvas: { width: 1440, height: 810 },
  canonical_station_canvas: { width: 1448, height: 1086 },
  guarantees: [],
  actors: {
    idle: {
      aligned_file: '04-actor/actor-idle-aligned.png',
      source_file: '04-actor/actor-idle-source.png',
      anchor: { x: 344, y: 205 },
      note: '',
    },
    work: {
      aligned_file: '04-actor/actor-work-aligned.png',
      source_file: '04-actor/actor-work-source.png',
      anchor: { x: 334, y: 205 },
      note: '',
    },
    sleep: {
      aligned_file: '04-actor/actor-sleep-aligned.png',
      source_file: '04-actor/actor-sleep-source.png',
      anchor: { x: 356, y: 217 },
      note: '',
    },
    error: {
      aligned_file: '04-actor/actor-error-aligned.png',
      source_file: '04-actor/actor-error-source.png',
      anchor: { x: 343, y: 235 },
      note: '',
    },
  },
  layers: [
    '01-background',
    '02-desk-base',
    '03-screen-overlay',
    '04-actor',
    '05-foreground-mask',
    '06-light-overlay',
    '07-fx-overlay',
    '08-label-ui',
  ],
}

describe('device office V2 asset contract', () => {
  it('loads the official fixed-canvas manifest and rejects invalid input', async () => {
    const validFetcher = vi.fn(
      async () => new Response(JSON.stringify(assetManifest), { status: 200 }),
    ) as unknown as typeof fetch
    expect((await loadDeviceOfficeAssetManifest(validFetcher)).version).toBe(
      '2.0',
    )
    expect(validFetcher).toHaveBeenCalledWith(DEVICE_OFFICE_MANIFEST_URL, {
      cache: 'force-cache',
    })

    const invalidFetcher = vi.fn(
      async () => new Response(JSON.stringify({ version: 1 }), { status: 200 }),
    ) as unknown as typeof fetch
    await expect(loadDeviceOfficeAssetManifest(invalidFetcher)).rejects.toThrow(
      'manifest is invalid',
    )
  })

  it('pairs every theme desk with its matching foreground mask', () => {
    const bundle = createDeviceOfficeAssetBundle(assetManifest)
    expect(bundle.themes.light.deskBase.src).toContain('desk-light-base.webp')
    expect(bundle.themes.light.foregroundMask.src).toContain(
      'desk-foreground-mask-light.webp',
    )
    expect(bundle.themes.dark.deskBase.src).toContain('desk-dark-base.webp')
    expect(bundle.themes.dark.foregroundMask.src).toContain(
      'desk-foreground-mask-dark.webp',
    )
  })

  it('maps approved aligned actor and screen assets without CSS recoloring', () => {
    const bundle = createDeviceOfficeAssetBundle(assetManifest)
    const provider = new ManifestActorAssetProvider(bundle)
    expect(
      provider.resolve({ actorState: 'idle', accentVariant: 'green' })?.src,
    ).toContain('actor-idle-aligned.png')
    expect(bundle.screens.onlineIdle.src).toContain('screen-idle-aligned.webp')
    expect(bundle.actors.sleep.src).toContain('actor-sleep-aligned.png')
    expect(bundle.fx.error.src).toContain('warning.png')
  })

  it('preloads background, desk, mask and light before showing a theme', async () => {
    const bundle = createDeviceOfficeAssetBundle(assetManifest)
    const preloader = vi.fn(async () => undefined)
    await preloadDeviceOfficeTheme(bundle.themes.dark, preloader)
    expect(preloader).toHaveBeenCalledTimes(4)
    expect(preloader.mock.calls.flat()).toEqual(
      expect.arrayContaining([
        bundle.themes.dark.background.src,
        bundle.themes.dark.deskBase.src,
        bundle.themes.dark.foregroundMask.src,
        bundle.themes.dark.lightOverlay.src,
      ]),
    )
  })
})
