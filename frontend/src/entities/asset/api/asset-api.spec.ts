import { afterEach, describe, expect, it, vi } from 'vitest'

import { httpClient } from '@/shared/api'

import {
  fetchAssetDownload,
  fetchAssetContent,
  getAssetContentUrl,
  getAssetThumbnailUrl,
} from './asset-api'

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

  it('keeps original and thumbnail routes explicitly separate', () => {
    expect(getAssetContentUrl('asset-1')).toBe('/api/v1/assets/asset-1/content')
    expect(getAssetThumbnailUrl('asset-1')).toBe(
      '/api/v1/assets/asset-1/thumbnail',
    )
  })

  it('downloads only the original content route with progress and a longer timeout', async () => {
    const blob = new Blob(['original'], { type: 'image/png' })
    const progress: Array<{ loadedBytes: number; totalBytes: number | null }> = []
    const get = vi.spyOn(httpClient, 'get').mockResolvedValue({ data: blob })
    const controller = new AbortController()

    await expect(
      fetchAssetDownload('/api/v1/assets/asset-1/content', {
        signal: controller.signal,
        onProgress: (value) => progress.push(value),
      }),
    ).resolves.toBe(blob)

    const config = get.mock.calls[0]?.[1]
    expect(get).toHaveBeenCalledWith('/api/v1/assets/asset-1/content', {
      responseType: 'blob',
      signal: controller.signal,
      timeout: 120_000,
      onDownloadProgress: expect.any(Function),
    })
    config?.onDownloadProgress?.({
      loaded: 12,
      total: 24,
      bytes: 12,
      lengthComputable: true,
    })
    expect(progress).toEqual([{ loadedBytes: 12, totalBytes: 24 }])
  })

  it('never turns a thumbnail URL into a download request', async () => {
    const get = vi.spyOn(httpClient, 'get')

    await expect(
      fetchAssetDownload('/api/v1/assets/asset-1/thumbnail'),
    ).rejects.toThrow('下载必须使用资产原图读取地址')
    expect(get).not.toHaveBeenCalled()
  })
})
