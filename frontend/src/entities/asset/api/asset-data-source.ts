import { apiMode, type ApiMode, type PageResult } from '@/shared/api'

import type { AssetListItemViewModel } from '../model/types'
import { assetApi, getAssetContentUrl } from './asset-api'
import { mapAssetDto } from './asset-mapper'
import type { AssetReadDto } from './contracts'

export interface AssetListParams {
  page: number
  pageSize: number
  search: string
}

export interface AssetDataSource {
  readonly mode: ApiMode
  list(params: AssetListParams): Promise<PageResult<AssetListItemViewModel>>
  upload(file: File): Promise<AssetListItemViewModel>
  remove(assetId: string): Promise<void>
}

const MOCK_THUMBNAIL =
  'data:image/svg+xml;charset=utf-8,' +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="64"><rect width="96" height="64" rx="6" fill="#dbeafe"/><path d="M16 48l20-20 13 13 9-9 22 16" fill="none" stroke="#3b82f6" stroke-width="5"/><circle cx="67" cy="19" r="6" fill="#3b82f6"/></svg>',
  )

function createMockDataSource(): AssetDataSource {
  const now = new Date().toISOString()
  const items: AssetReadDto[] = [
    {
      asset_id: '20000000-0000-4000-8000-000000000001',
      media_type: 'image',
      original_filename: 'test-01.jpg',
      content_type: 'image/jpeg',
      size_bytes: 124_320,
      sha256: 'a'.repeat(64),
      source_type: 'upload',
      created_at: now,
    },
    {
      asset_id: '20000000-0000-4000-8000-000000000002',
      media_type: 'image',
      original_filename: 'test-02.png',
      content_type: 'image/png',
      size_bytes: 245_760,
      sha256: 'b'.repeat(64),
      source_type: 'upload',
      created_at: now,
    },
  ]
  return {
    mode: 'mock',
    async list(params) {
      const search = params.search.trim().toLocaleLowerCase()
      const filtered = items.filter(
        (item) =>
          !search || item.original_filename.toLocaleLowerCase().includes(search),
      )
      const start = (params.page - 1) * params.pageSize
      return {
        items: filtered
          .slice(start, start + params.pageSize)
          .map((item) => mapAssetDto(item, MOCK_THUMBNAIL)),
        total: filtered.length,
        page: params.page,
        pageSize: params.pageSize,
      }
    },
    async upload(file) {
      const dto: AssetReadDto = {
        asset_id: crypto.randomUUID(),
        media_type: 'image',
        original_filename: file.name,
        content_type: file.type,
        size_bytes: file.size,
        sha256: '0'.repeat(64),
        source_type: 'upload',
        created_at: new Date().toISOString(),
      }
      items.unshift(dto)
      return mapAssetDto(dto, MOCK_THUMBNAIL)
    },
    async remove(assetId) {
      const index = items.findIndex((item) => item.asset_id === assetId)
      if (index >= 0) items.splice(index, 1)
    },
  }
}

const realDataSource: AssetDataSource = {
  mode: 'real',
  async list(params) {
    const page = await assetApi.list(params)
    return {
      items: page.items.map((item) =>
        mapAssetDto(item, getAssetContentUrl(item.asset_id)),
      ),
      total: page.total,
      page: page.page,
      pageSize: page.page_size,
    }
  },
  async upload(file) {
    const dto = await assetApi.upload(file)
    return mapAssetDto(dto, getAssetContentUrl(dto.asset_id))
  },
  remove: assetApi.remove,
}

export function createAssetDataSource(mode: ApiMode): AssetDataSource {
  return mode === 'real' ? realDataSource : createMockDataSource()
}

export const assetDataSource = createAssetDataSource(apiMode)
