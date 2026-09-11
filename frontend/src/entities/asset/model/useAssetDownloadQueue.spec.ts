import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('../api/asset-api', () => ({
  fetchAssetDownload: vi.fn(),
}))

import { fetchAssetDownload } from '../api/asset-api'
import { ApiError } from '@/shared/api'

import { useAssetDownloadQueue } from './useAssetDownloadQueue'

const download = vi.mocked(fetchAssetDownload)

function prepareBrowserDownload(): void {
  vi.stubGlobal('URL', {
    createObjectURL: vi.fn(() => 'blob:asset-download'),
    revokeObjectURL: vi.fn(),
  })
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
}

describe('asset download queue', () => {
  afterEach(() => {
    vi.runAllTimers()
    vi.useRealTimers()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('deduplicates requests and caps concurrent original-file downloads', async () => {
    prepareBrowserDownload()
    vi.useFakeTimers()
    let active = 0
    let maxActive = 0
    download.mockImplementation(async (_url, options) => {
      active += 1
      maxActive = Math.max(maxActive, active)
      options?.onProgress?.({ loadedBytes: 10, totalBytes: 10 })
      await Promise.resolve()
      active -= 1
      return new Blob(['asset'])
    })
    const queue = useAssetDownloadQueue({ concurrency: 2 })

    const summary = await queue.start([
      { id: 'a', contentUrl: '/api/v1/assets/a/content', filename: 'a.png' },
      { id: 'a', contentUrl: '/api/v1/assets/a/content', filename: 'a.png' },
      { id: 'b', contentUrl: '/api/v1/assets/b/content', filename: 'b.png' },
      { id: 'c', contentUrl: '/api/v1/assets/c/content', filename: 'c.png' },
    ])

    expect(summary).toMatchObject({ succeeded: 3, failed: 0, cancelled: 0 })
    expect(download).toHaveBeenCalledTimes(3)
    expect(maxActive).toBe(2)
    expect(queue.progressLabel.value).toBe('3 / 3')
    expect(queue.failedRequests.value).toEqual([])
    await vi.runAllTimersAsync()
  })

  it('retries only failed downloads and leaves cancelled work out of retry', async () => {
    prepareBrowserDownload()
    vi.useFakeTimers()
    const failed = new ApiError({
      code: 'ASSET_NOT_FOUND',
      message: '图片不存在',
      requestId: 'request-failed',
      status: 404,
    })
    const cancelled = new ApiError({
      code: 'REQUEST_CANCELLED',
      message: '请求已取消',
    })
    download
      .mockResolvedValueOnce(new Blob(['first']))
      .mockRejectedValueOnce(failed)
      .mockRejectedValueOnce(cancelled)
      .mockResolvedValueOnce(new Blob(['retry']))
    const queue = useAssetDownloadQueue({ concurrency: 1 })

    const first = await queue.start([
      { id: 'ok', contentUrl: '/api/v1/assets/ok/content', filename: 'ok.png' },
      { id: 'failed', contentUrl: '/api/v1/assets/failed/content', filename: 'failed.png' },
      { id: 'cancelled', contentUrl: '/api/v1/assets/cancelled/content', filename: 'cancelled.png' },
    ])

    expect(first).toMatchObject({ succeeded: 1, failed: 1, cancelled: 1 })
    expect(queue.failedRequests.value).toEqual([
      {
        id: 'failed',
        contentUrl: '/api/v1/assets/failed/content',
        filename: 'failed.png',
      },
    ])

    const retry = await queue.retryFailed()
    expect(retry).toMatchObject({ succeeded: 1, failed: 0, cancelled: 0 })
    expect(download).toHaveBeenCalledTimes(4)
    expect(download.mock.calls[3]?.[0]).toBe('/api/v1/assets/failed/content')
    await vi.runAllTimersAsync()
  })
})
