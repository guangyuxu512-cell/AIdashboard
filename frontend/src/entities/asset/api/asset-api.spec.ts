import { afterEach, describe, expect, it, vi } from 'vitest'

import { httpClient } from '@/shared/api'

import { fetchAssetContent } from './asset-api'

describe('asset content api', () => {
  afterEach(() => vi.restoreAllMocks())

  it('loads protected content through the shared human request context', async () => {
    const blob = new Blob(['asset'], { type: 'image/png' })
    const get = vi.spyOn(httpClient, 'get').mockResolvedValue({ data: blob })
    const controller = new AbortController()

    await expect(
      fetchAssetContent('/api/v1/assets/asset-1/content', controller.signal),
    ).resolves.toBe(blob)
    expect(get).toHaveBeenCalledWith('/api/v1/assets/asset-1/content', {
      responseType: 'blob',
      signal: controller.signal,
    })
  })
})
