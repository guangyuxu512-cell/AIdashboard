export type ShopSessionStatusDto =
  | 'not_configured'
  | 'captured'
  | 'valid'
  | 'invalid'
  | 'refresh_required'

export interface ShopSessionMetadataReadDto {
  session_id: string | null
  configured: boolean
  status: ShopSessionStatusDto
  version: number
  source_device_id: string | null
  captured_at: string | null
  validated_at: string | null
  expires_at: string | null
}
