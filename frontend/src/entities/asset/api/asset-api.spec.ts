import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, httpClient } from '@/shared/api'

import {
  assetApi,
  assetPreviewTimeoutMs,
  formatAssetOperationFailure,
  fetchAssetDownload,
  fetchAssetContent,
  getAssetContentUrl,
  getAssetThumbnailUrl,
} from './asset-api'

describe('asset content api', () => {
  afterEach(() => vi.restoreAllMocks())

  it.each([
    [new ApiError({ message: 'Request failed', status: 413 }), '10 MiB', 'HTTP_413'],
    [new ApiError({ message: 'Team required', code: 'TEAM_CONTEXT_REQUIRED', status: 409 }), '选择业务团队', 'TEAM_CONTEXT_REQUIRED'],
    [new ApiError({ message: 'Module denied', code: 'MODULE_ACCESS_DENIED', status: 403, requestId: 'request-1' }), '没有此素材操作权限', 'request-1'],
    [new ApiError({ message: 'Timeout', code: 'REQUEST_TIMEOUT' }), '结果尚未确认', 'REQUEST_TIMEOUT'],
  ] as const)('keeps bounded upload failure semantics and request diagnostics', (failure, description, diagnostic) => {
    const message = formatAssetOperationFailure(failure, '上传 input.jpg')
    expect(message).toContain('上传 input.jpg')
    expect(message).toContain(description)
    expect(message).toContain(diagnostic)
  })

  it('does not automatically retransmit an upload after an uncertain failure', async () => {
    const post = vi.spyOn(httpClient, 'post').mockRejectedValue(new ApiError({ message: 'Timeout', code: 'REQUEST_TIMEOUT' }))
    await expect(assetApi.upload(new File(['image'], 'input.jpg'))).rejects.toMatchObject({ code: 'REQUEST_TIMEOUT' })
    expect(post).toHaveBeenCalledTimes(1)
    expect(httpClient.defaults.timeout).toBe(10_000)
  })

  it('uses a bounded upload-specific timeout instead of the shared ten seconds', async () => {
    const file = new File(['image'], 'input.png', { type: 'image/png' })
    const post = vi
      .spyOn(httpClient, 'post')
      .mockResolvedValue({ data: { asset_id: 'new' } })
    await assetApi.upload(file)
    expect(post).toHaveBeenCalledWith('/api/v1/assets', expect.any(FormData), {
      timeout: 120_000,
    })
    expect((post.mock.calls[0]![1] as FormData).get('file')).toMatchObject({
      name: file.name,
      size: file.size,
      type: file.type,
    })
  })

  it('rejects an image above the ten MiB contract before transmitting it', async () => {
    const file = new File(['image'], 'large.png', { type: 'image/png' })
    Object.defineProperty(file, 'size', { value: 10 * 1024 * 1024 + 1 })
    const post = vi.spyOn(httpClient, 'post').mockResolvedValue({ data: {} })
    await expect(assetApi.upload(file)).rejects.toMatchObject({
      code: 'ASSET_TOO_LARGE',
    })
    expect(post).not.toHaveBeenCalled()
  })

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

  it('allows full-image previews to use their bounded preview timeout', async () => {
    const blob = new Blob(['asset'], { type: 'image/png' })
    const get = vi.spyOn(httpClient, 'get').mockResolvedValue({ data: blob })
    const controller = new AbortController()

    await expect(
      fetchAssetContent('/api/v1/assets/asset-1/content', controller.signal, {
        timeoutMs: assetPreviewTimeoutMs,
      }),
    ).resolves.toBe(blob)
    expect(get).toHaveBeenCalledWith('/api/v1/assets/asset-1/content', {
      responseType: 'blob',
      signal: controller.signal,
      timeout: assetPreviewTimeoutMs,
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
    const progress: Array<{ loadedBytes: number; totalBytes: number | null }> =
      []
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
