import { LoadingManager } from 'three'
import { GLTFLoader, type GLTF } from 'three/examples/jsm/loaders/GLTFLoader.js'

import {
  OFFICE_ASSET_KEYS,
  officeAssetManifest,
  type OfficeAssetDefinition,
  type OfficeAssetKey,
} from './office-asset-manifest'

export interface OfficeAssetBundle {
  assets: Record<OfficeAssetKey, GLTF>
}

export interface OfficeAssetAvailability {
  ready: boolean
  missing: OfficeAssetDefinition[]
}

export class OfficeAssetContractError extends Error {
  constructor(
    readonly asset: OfficeAssetDefinition,
    readonly missingNodes: string[],
    readonly missingAnimations: string[],
  ) {
    super(`Office asset contract mismatch: ${asset.key}`)
    this.name = 'OfficeAssetContractError'
  }
}

type AssetProbe = (url: string) => Promise<boolean>

async function defaultAssetProbe(url: string): Promise<boolean> {
  try {
    const response = await fetch(url, { method: 'HEAD', cache: 'no-store' })
    if (!response.ok) return false
    return !response.headers.get('content-type')?.includes('text/html')
  } catch {
    return false
  }
}

export async function checkOfficeAssetAvailability(
  probe: AssetProbe = defaultAssetProbe,
): Promise<OfficeAssetAvailability> {
  const results = await Promise.all(
    OFFICE_ASSET_KEYS.map(async (key) => ({
      asset: officeAssetManifest[key],
      exists: await probe(officeAssetManifest[key].url),
    })),
  )
  const missing = results.filter((result) => !result.exists).map((result) => result.asset)
  return { ready: missing.length === 0, missing }
}

function validateAsset(asset: OfficeAssetDefinition, gltf: GLTF): void {
  const missingNodes = asset.requiredNodes.filter(
    (nodeName) => gltf.scene.getObjectByName(nodeName) === undefined,
  )
  const animationNames = new Set(gltf.animations.map((clip) => clip.name))
  const missingAnimations = asset.requiredAnimations.filter(
    (clipName) => !animationNames.has(clipName),
  )
  if (missingNodes.length || missingAnimations.length) {
    throw new OfficeAssetContractError(asset, missingNodes, missingAnimations)
  }
}

export async function loadOfficeAssetBundle(
  loadingManager = new LoadingManager(),
): Promise<OfficeAssetBundle> {
  const loader = new GLTFLoader(loadingManager)
  const entries = await Promise.all(
    OFFICE_ASSET_KEYS.map(async (key) => {
      const definition = officeAssetManifest[key]
      const gltf = await loader.loadAsync(definition.url)
      validateAsset(definition, gltf)
      return [key, gltf] as const
    }),
  )
  return { assets: Object.fromEntries(entries) as Record<OfficeAssetKey, GLTF> }
}

