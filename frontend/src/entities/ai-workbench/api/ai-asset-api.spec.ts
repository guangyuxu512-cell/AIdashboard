import { afterEach, describe, expect, it, vi } from 'vitest'

import { httpClient } from '@/shared/api'
import { aiAssetApi, getAiAssetContentUrl, getAiAssetThumbnailUrl } from './ai-asset-api'

describe('AI-scoped file API', () => {
  afterEach(() => vi.restoreAllMocks())

  it('uploads once with the shared file body and bounded timeout, never to the general library', async () => {
    const post = vi.spyOn(httpClient, 'post').mockResolvedValue({ data: { asset_id: 'one' } })
    await expect(aiAssetApi.upload(new File(['image'], 'one.jpg'))).resolves.toEqual({ asset_id: 'one' })
    expect(post).toHaveBeenCalledExactlyOnceWith('/api/v1/ai-workbench/assets', expect.any(FormData), { timeout: 120_000 })
  })

  it('uses the same AI authority for preview, thumbnail, download and explicit cleanup', async () => {
    expect(getAiAssetContentUrl('one')).toBe('/api/v1/ai-workbench/assets/one/content')
    expect(getAiAssetThumbnailUrl('one')).toBe('/api/v1/ai-workbench/assets/one/thumbnail')
    const remove = vi.spyOn(httpClient, 'delete').mockResolvedValue({ data: undefined })
    await aiAssetApi.cleanup('one')
    expect(remove).toHaveBeenCalledExactlyOnceWith('/api/v1/ai-workbench/assets/one')
  })
})
