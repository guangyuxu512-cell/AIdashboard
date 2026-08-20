import type { ResolvedTheme } from '@/stores/theme'

import type {
  DeviceAccentVariant,
  DeviceActorState,
  DeviceVisualState,
} from '../model/types'

export const DEVICE_OFFICE_MANIFEST_URL = '/assets/device-office/manifest.json'
export const REFERENCE_PREVIEW_MODE = 'REFERENCE_PREVIEW'
export const ART_ASSETS_PENDING = 'ART_ASSETS_PENDING'

export type DeviceOfficeAssetFormat =
  'image' | 'png-sequence' | 'sprite-sheet' | 'transparent-webm' | 'pag'

export interface DeviceOfficeAssetSource {
  format: DeviceOfficeAssetFormat
  src: string
  poster?: string
  frameCount?: number
  framesPerSecond?: number
}

export interface DeviceOfficeSceneAssets {
  background: DeviceOfficeAssetSource | null
  backEnvironment: DeviceOfficeAssetSource | null
  foreground: DeviceOfficeAssetSource | null
}

export interface DeviceOfficeAssetManifest {
  version: 2
  status: typeof ART_ASSETS_PENDING | 'READY'
  designCanvas: { width: number; height: number }
  scene: Record<ResolvedTheme, DeviceOfficeSceneAssets>
  actors: Record<DeviceActorState, DeviceOfficeAssetSource | null>
  screens: Record<DeviceVisualState, DeviceOfficeAssetSource | null>
  referencePreview: Record<ResolvedTheme, DeviceOfficeAssetSource | null>
}

export interface ActorAssetRequest {
  actorState: DeviceActorState
  accentVariant: DeviceAccentVariant
}

export interface ActorAssetProvider {
  resolve(request: ActorAssetRequest): DeviceOfficeAssetSource | null
}

export class ManifestActorAssetProvider implements ActorAssetProvider {
  constructor(private readonly manifest: DeviceOfficeAssetManifest) {}

  resolve(request: ActorAssetRequest): DeviceOfficeAssetSource | null {
    // Accent is a future art variant input. It deliberately does not recolor artwork in CSS.
    void request.accentVariant
    return this.manifest.actors[request.actorState]
  }
}

function isDeviceOfficeAssetManifest(
  value: unknown,
): value is DeviceOfficeAssetManifest {
  if (!value || typeof value !== 'object') return false
  const manifest = value as Partial<DeviceOfficeAssetManifest>
  return (
    manifest.version === 2 &&
    manifest.designCanvas?.width === 1440 &&
    manifest.designCanvas?.height === 810 &&
    manifest.scene !== undefined &&
    manifest.actors !== undefined &&
    manifest.screens !== undefined &&
    manifest.referencePreview !== undefined
  )
}

export async function loadDeviceOfficeAssetManifest(
  fetcher: typeof fetch = fetch,
): Promise<DeviceOfficeAssetManifest> {
  const response = await fetcher(DEVICE_OFFICE_MANIFEST_URL, {
    cache: 'no-store',
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
