import { apiBaseUrl, httpClient } from '@/shared/api'
import type { PageDto } from '@/shared/api'

import type { AssetReadDto } from './contracts'

export const assetDownloadTimeoutMs = 120_000
export const assetPreviewTimeoutMs = 30_000

export interface AssetDownloadProgress {
  loadedBytes: number
  totalBytes: number | null
}

export interface AssetDownloadOptions {
  signal?: AbortSignal
  onProgress?: (progress: AssetDownloadProgress) => void
}

export interface AssetContentRequestOptions {
  timeoutMs?: number
}

export interface AssetListApiParams {
  page: number
  pageSize: number
  search: string
}

function getAssetUrl(
  assetId: string,
  resource: 'content' | 'thumbnail',
): string {
  const path = `/api/v1/assets/${encodeURIComponent(assetId)}/${resource}`
  if (/^https?:\/\//i.test(apiBaseUrl)) {
    return new URL(path, apiBaseUrl).toString()
  }
  return path
}

export function getAssetContentUrl(assetId: string): string {
  return getAssetUrl(assetId, 'content')
}

export function getAssetThumbnailUrl(assetId: string): string {
  return getAssetUrl(assetId, 'thumbnail')
}

export async function fetchAssetContent(
  contentUrl: string,
  signal?: AbortSignal,
  options: AssetContentRequestOptions = {},
): Promise<Blob> {
  const response = await httpClient.get<Blob>(contentUrl, {
    responseType: 'blob',
    signal,
    ...(options.timeoutMs === undefined ? {} : { timeout: options.timeoutMs }),
  })
  return response.data
}

export async function fetchAssetDownload(
  contentUrl: string,
  options: AssetDownloadOptions = {},
): Promise<Blob> {
  if (/\/thumbnail(?:[/?#]|$)/.test(contentUrl)) {
    throw new Error('下载必须使用资产原图读取地址')
  }
  const response = await httpClient.get<Blob>(contentUrl, {
    responseType: 'blob',
    signal: options.signal,
    timeout: assetDownloadTimeoutMs,
    onDownloadProgress: (event) => {
      options.onProgress?.({
        loadedBytes: event.loaded,
        totalBytes: event.total ?? null,
      })
    },
  })
  return response.data
}

export const assetApi = {
  async list(params: AssetListApiParams): Promise<PageDto<AssetReadDto>> {
    const response = await httpClient.get<PageDto<AssetReadDto>>(
      '/api/v1/assets',
      {
        params: {
          page: params.page,
          page_size: params.pageSize,
          search: params.search.trim() || undefined,
        },
      },
    )
    return response.data
  },

  async upload(file: File): Promise<AssetReadDto> {
    const form = new FormData()
    form.append('file', file, file.name)
    const response = await httpClient.post<AssetReadDto>('/api/v1/assets', form)
    return response.data
  },

  async remove(assetId: string): Promise<void> {
    await httpClient.delete(`/api/v1/assets/${assetId}`)
  },
}
