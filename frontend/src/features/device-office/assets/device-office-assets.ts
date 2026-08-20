import type { ResolvedTheme } from '@/stores/theme'

import type {
  DeviceAccentVariant,
  DeviceActorState,
  DeviceVisualState,
} from '../model/types'

export const DEVICE_OFFICE_ASSET_ROOT = '/assets/device-office/v2'
export const DEVICE_OFFICE_MANIFEST_URL = `${DEVICE_OFFICE_ASSET_ROOT}/manifest.json`

export interface DeviceOfficeAssetSource {
  format: 'image'
  src: string
}

export interface DeviceOfficePackActor {
  aligned_file: string
  source_file: string
  anchor: { x: number; y: number }
  note: string
}

export interface DeviceOfficeAssetManifest {
  name: string
  version: '2.0'
  design_canvas: { width: 1440; height: 810 }
  canonical_station_canvas: { width: 1448; height: 1086 }
  guarantees: string[]
  actors: Record<'idle' | 'work' | 'sleep' | 'error', DeviceOfficePackActor>
  layers: string[]
}

export interface DeviceOfficeThemeAssets {
  background: DeviceOfficeAssetSource
  deskBase: DeviceOfficeAssetSource
  foregroundMask: DeviceOfficeAssetSource
  lightOverlay: DeviceOfficeAssetSource
}

export interface DeviceOfficeAssetBundle {
  themes: Record<ResolvedTheme, DeviceOfficeThemeAssets>
  actors: Record<'idle' | 'work' | 'sleep' | 'error', DeviceOfficeAssetSource>
  screens: Record<Exclude<DeviceVisualState, 'empty'>, DeviceOfficeAssetSource>
  fx: Record<'offline' | 'error', DeviceOfficeAssetSource>
}

export interface ActorAssetRequest {
  actorState: DeviceActorState
  accentVariant: DeviceAccentVariant
}

export interface ActorAssetProvider {
  resolve(request: ActorAssetRequest): DeviceOfficeAssetSource | null
}

function image(src: string): DeviceOfficeAssetSource {
  return { format: 'image', src }
}

function asset(relativePath: string): DeviceOfficeAssetSource {
  if (
    relativePath.startsWith('/') ||
    relativePath.includes('..') ||
    relativePath.includes('\\')
  ) {
    throw new Error(`Invalid Device Office asset path: ${relativePath}`)
  }
  return image(`${DEVICE_OFFICE_ASSET_ROOT}/${relativePath}`)
}

export function createDeviceOfficeAssetBundle(
  manifest: DeviceOfficeAssetManifest,
): DeviceOfficeAssetBundle {
  return {
    themes: {
      light: {
        background: asset('01-background/office-light-background.webp'),
        deskBase: asset('02-desk-base/desk-light-base.webp'),
        foregroundMask: asset(
          '05-foreground-mask/desk-foreground-mask-light.webp',
        ),
        lightOverlay: asset('06-light-overlay/lamp-glow-light.webp'),
      },
      dark: {
        background: asset('01-background/office-dark-background.webp'),
        deskBase: asset('02-desk-base/desk-dark-base.webp'),
        foregroundMask: asset(
          '05-foreground-mask/desk-foreground-mask-dark.webp',
        ),
        lightOverlay: asset('06-light-overlay/lamp-glow-dark.webp'),
      },
    },
    actors: {
      idle: asset(manifest.actors.idle.aligned_file),
      work: asset(manifest.actors.work.aligned_file),
      sleep: asset(manifest.actors.sleep.aligned_file),
      error: asset(manifest.actors.error.aligned_file),
    },
    screens: {
      onlineIdle: asset('03-screen-overlay/screen-idle-aligned.webp'),
      busy: asset('03-screen-overlay/screen-busy-aligned.webp'),
      offline: asset('03-screen-overlay/screen-offline-aligned.webp'),
      error: asset('03-screen-overlay/screen-error-aligned.webp'),
    },
    fx: {
      offline: asset('07-fx-overlay/zzz.png'),
      error: asset('07-fx-overlay/warning.png'),
    },
  }
}

export class ManifestActorAssetProvider implements ActorAssetProvider {
  constructor(private readonly bundle: DeviceOfficeAssetBundle) {}

  resolve(request: ActorAssetRequest): DeviceOfficeAssetSource | null {
    // V2 ships one approved actor treatment. Accent remains a provider input
    // so a future art bundle can add variants without touching Device state.
    void request.accentVariant
    if (
      request.actorState === 'coffee' ||
      request.actorState === 'walk' ||
      request.actorState === 'celebrate'
    ) {
      return null
    }
    return this.bundle.actors[request.actorState]
  }
}

function isDeviceOfficeAssetManifest(
  value: unknown,
): value is DeviceOfficeAssetManifest {
  if (!value || typeof value !== 'object') return false
  const manifest = value as Partial<DeviceOfficeAssetManifest>
  return (
    manifest.version === '2.0' &&
    manifest.design_canvas?.width === 1440 &&
    manifest.design_canvas?.height === 810 &&
    manifest.canonical_station_canvas?.width === 1448 &&
    manifest.canonical_station_canvas?.height === 1086 &&
    manifest.actors?.idle?.aligned_file !== undefined &&
    manifest.actors?.work?.aligned_file !== undefined &&
    manifest.actors?.sleep?.aligned_file !== undefined &&
    manifest.actors?.error?.aligned_file !== undefined &&
    Array.isArray(manifest.layers) &&
    manifest.layers.length === 8
  )
}

export async function loadDeviceOfficeAssetManifest(
  fetcher: typeof fetch = fetch,
): Promise<DeviceOfficeAssetManifest> {
  const response = await fetcher(DEVICE_OFFICE_MANIFEST_URL, {
    cache: 'force-cache',
  })
  if (!response.ok) {
    throw new Error(
      `Device Office asset manifest unavailable: ${response.status}`,
    )
  }
  const manifest: unknown = await response.json()
  if (!isDeviceOfficeAssetManifest(manifest)) {
    throw new Error('Device Office asset manifest is invalid')
  }
  return manifest
}

export type OfficeImagePreloader = (src: string) => Promise<void>

export async function preloadImage(src: string): Promise<void> {
  const preload = new Image()
  preload.decoding = 'async'
  preload.src = src
  if (preload.decode) {
    await preload.decode()
    return
  }
  await new Promise<void>((resolve, reject) => {
    preload.onload = () => resolve()
    preload.onerror = () => reject(new Error(`Office asset failed: ${src}`))
  })
}

export async function preloadDeviceOfficeTheme(
  assets: DeviceOfficeThemeAssets,
  preloader: OfficeImagePreloader = preloadImage,
): Promise<void> {
  await Promise.all(
    [
      assets.background.src,
      assets.deskBase.src,
      assets.foregroundMask.src,
      assets.lightOverlay.src,
    ].map(preloader),
  )
}
