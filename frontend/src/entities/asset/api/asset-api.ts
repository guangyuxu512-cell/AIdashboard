import { ApiError, apiBaseUrl, httpClient, toApiError } from '@/shared/api'
import type { PageDto } from '@/shared/api'

import type { AssetReadDto } from './contracts'

export const assetDownloadTimeoutMs = 120_000
export const assetPreviewTimeoutMs = 30_000
export const assetUploadTimeoutMs = 120_000
// Product upload contract; Backend validation always remains authoritative.
export const assetMaxUploadBytes = 10 * 1024 * 1024

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
  basePath = '/api/v1/assets',
): string {
  const path = `${basePath}/${encodeURIComponent(assetId)}/${resource}`
  if (/^https?:\/\//i.test(apiBaseUrl)) {
    return new URL(path, apiBaseUrl).toString()
  }
  return path
}

export function getAssetContentUrl(assetId: string, basePath?: string): string {
  return getAssetUrl(assetId, 'content', basePath)
}

export function getAssetThumbnailUrl(
  assetId: string,
  basePath?: string,
): string {
  return getAssetUrl(assetId, 'thumbnail', basePath)
}

export async function uploadAssetFile(
  file: File,
  path = '/api/v1/assets',
): Promise<AssetReadDto> {
  if (file.size > assetMaxUploadBytes) {
    throw new ApiError({
      code: 'ASSET_TOO_LARGE',
      status: 413,
      message: '单张图片不能超过 10 MiB',
    })
  }
  const form = new FormData()
  form.append('file', file, file.name)
  const response = await httpClient.post<AssetReadDto>(path, form, {
    timeout: assetUploadTimeoutMs,
  })
  return response.data
}

export function formatAssetOperationFailure(
  error: unknown,
  phase = '上传图片',
): string {
  const failure = toApiError(error)
  const description =
    failure.status === 413
      ? '图片超过大小限制，单张图片不能超过 10 MiB'
      : failure.code === 'TEAM_CONTEXT_REQUIRED'
        ? '请先选择业务团队'
        : failure.code === 'MODULE_ACCESS_DENIED'
          ? '当前账号没有此素材操作权限，请联系管理员检查授权'
          : failure.code === 'REQUEST_TIMEOUT'
            ? '请求超时，结果尚未确认，请先刷新检查后再试'
            : failure.message
  const code =
    failure.status && failure.code === 'NETWORK_ERROR'
      ? `HTTP_${failure.status}`
      : failure.code
  return `${phase}：${description} [${code}]${failure.requestId ? ` 请求编号：${failure.requestId}` : ''}`
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
    return uploadAssetFile(file)
  },

  async remove(assetId: string): Promise<void> {
    await httpClient.delete(`/api/v1/assets/${assetId}`)
  },
}
