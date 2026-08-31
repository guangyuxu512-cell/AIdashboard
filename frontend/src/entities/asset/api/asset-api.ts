import { apiBaseUrl, httpClient } from '@/shared/api'
import type { PageDto } from '@/shared/api'

import type { AssetReadDto } from './contracts'

export interface AssetListApiParams {
  page: number
  pageSize: number
  search: string
}

export function getAssetContentUrl(assetId: string): string {
  const path = `/api/v1/assets/${encodeURIComponent(assetId)}/content`
  if (/^https?:\/\//i.test(apiBaseUrl)) {
    return new URL(path, apiBaseUrl).toString()
  }
  return path
}

export async function fetchAssetContent(
  contentUrl: string,
  signal?: AbortSignal,
): Promise<Blob> {
  const response = await httpClient.get<Blob>(contentUrl, {
    responseType: 'blob',
    signal,
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
