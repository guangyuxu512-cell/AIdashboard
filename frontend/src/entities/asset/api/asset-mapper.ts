import dayjs from 'dayjs'

import type { AssetListItemViewModel } from '../model/types'
import type { AssetReadDto } from './contracts'

export function formatAssetSize(sizeBytes: number): string {
  if (sizeBytes < 1024) return `${sizeBytes} B`
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`
  return `${(sizeBytes / (1024 * 1024)).toFixed(1)} MB`
}

export function mapAssetDto(
  dto: AssetReadDto,
  contentUrl: string,
): AssetListItemViewModel {
  return {
    assetId: dto.asset_id,
    filename: dto.original_filename,
    contentType: dto.content_type,
    sizeBytes: dto.size_bytes,
    sizeDisplay: formatAssetSize(dto.size_bytes),
    sha256: dto.sha256,
    createdAt: dto.created_at,
    createdAtDisplay: dayjs(dto.created_at).format('YYYY-MM-DD HH:mm'),
    contentUrl,
  }
}
