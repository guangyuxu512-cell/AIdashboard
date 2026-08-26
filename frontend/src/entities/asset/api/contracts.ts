export type AssetMediaTypeDto = 'image' | 'video'

export type AssetSourceTypeDto = 'upload' | 'ai_generated' | 'imported'

export interface AssetReadDto {
  asset_id: string
  media_type: AssetMediaTypeDto
  original_filename: string
  content_type: string
  size_bytes: number
  sha256: string
  source_type: AssetSourceTypeDto
  created_at: string
}
