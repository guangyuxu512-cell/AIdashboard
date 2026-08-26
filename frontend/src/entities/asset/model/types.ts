export type AssetMediaType = 'image' | 'video'

export type AssetSourceType = 'upload' | 'ai_generated' | 'imported'

export interface AssetListItemViewModel {
  assetId: string
  mediaType: AssetMediaType
  filename: string
  contentType: string
  sizeBytes: number
  sizeDisplay: string
  sha256: string
  sourceType: AssetSourceType
  createdAt: string
  createdAtDisplay: string
  contentUrl: string
}
