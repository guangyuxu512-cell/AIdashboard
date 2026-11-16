import { shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { assetPreviewTimeoutMs } from '@/entities/asset/api/asset-api'
import { AssetContentImage } from '@/entities/asset'

import type { MaterialAssetReference } from '../model/types'
import MaterialAssetInspector from './MaterialAssetInspector.vue'

const asset: MaterialAssetReference = {
  assetId: 'generated-asset-1',
  name: 'AI成品.png',
  mediaType: 'image/png',
  sourceType: 'AI_GENERATION',
  role: 'AI_OUTPUT',
  previewUrl: '/api/v1/assets/generated-asset-1/content',
  thumbnailUrl: '/api/v1/assets/generated-asset-1/thumbnail',
  sizeBytes: 4_900_000,
}

describe('MaterialAssetInspector', () => {
  it('keeps a thumbnail visible while the authenticated full asset loads', () => {
    const wrapper = shallowMount(MaterialAssetInspector, { props: { asset } })
    const image = wrapper.findComponent(AssetContentImage)

    expect(image.props()).toMatchObject({
      src: asset.previewUrl,
      fallbackSrc: asset.thumbnailUrl,
      loading: 'eager',
      timeoutMs: assetPreviewTimeoutMs,
      interactive: true,
    })
  })
})
