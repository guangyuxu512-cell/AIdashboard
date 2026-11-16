import { describe, expect, it } from 'vitest'

import type { GenerationProductView } from './types'
import {
  countGenerationProductSourceAssets,
  getGenerationProductSourceAssets,
} from './product-source-assets'

const product: GenerationProductView = {
  id: 'product-1',
  name: '餐盘',
  enabled: true,
  normalGenerationEnabled: true,
  styleReplicationEnabled: false,
  normalTemplateGroupIds: [],
  styleReplicationTemplateGroupIds: [],
  assets: [
    {
      id: 'source-1',
      name: '餐盘正面.png',
      previewUrl: '/api/v1/assets/source-1/content',
      role: 'PRODUCT_SOURCE',
      sourceType: 'ASSET_LIBRARY',
    },
    {
      id: 'source-2',
      name: '餐盘侧面.png',
      previewUrl: '/api/v1/assets/source-2/content',
      role: 'PRODUCT_SOURCE',
      sourceType: 'ASSET_LIBRARY',
    },
    ...Array.from({ length: 8 }, (_, index) => ({
      id: `output-${index + 1}`,
      name: `AI成品-${index + 1}.png`,
      previewUrl: `/api/v1/assets/output-${index + 1}/content`,
      role: 'AI_OUTPUT' as const,
      sourceType: 'ASSET_LIBRARY' as const,
    })),
  ],
}

describe('generation product source assets', () => {
  it('counts only PRODUCT_SOURCE when generated outputs share a product', () => {
    expect(product.assets).toHaveLength(10)
    expect(countGenerationProductSourceAssets(product)).toBe(2)
    expect(
      getGenerationProductSourceAssets(product.assets).map((asset) => asset.id),
    ).toEqual(['source-1', 'source-2'])
  })
})
