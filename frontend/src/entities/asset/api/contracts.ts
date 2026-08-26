export interface AssetReadDto {
  asset_id: string
  original_filename: string
  content_type: 'image/jpeg' | 'image/png' | 'image/webp'
  size_bytes: number
  sha256: string
  created_at: string
}
