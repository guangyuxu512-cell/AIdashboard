import { describe, expect, it } from 'vitest'

import { mapAssetDto } from './asset-mapper'

describe('asset mapper', () => {
  it('maps the Asset Foundation V2 media and source semantics', () => {
    const asset = mapAssetDto(
      {
        asset_id: '20000000-0000-4000-8000-000000000001',
        media_type: 'image',
        source_type: 'upload',
        original_filename: 'product.png',
        content_type: 'image/png',
        size_bytes: 1024,
        sha256: 'a'.repeat(64),
        created_at: '2026-08-26T00:00:00Z',
      },
      '/api/v1/assets/20000000-0000-4000-8000-000000000001/content',
      '/api/v1/assets/20000000-0000-4000-8000-000000000001/thumbnail',
    )

    expect(asset).toMatchObject({
      mediaType: 'image',
      sourceType: 'upload',
      contentType: 'image/png',
      contentUrl:
        '/api/v1/assets/20000000-0000-4000-8000-000000000001/content',
      thumbnailUrl:
        '/api/v1/assets/20000000-0000-4000-8000-000000000001/thumbnail',
    })
  })
})
