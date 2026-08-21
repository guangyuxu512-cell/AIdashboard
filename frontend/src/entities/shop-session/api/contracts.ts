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
  refresh_in_progress: boolean
  refresh_lease_expires_at: string | null
}

export interface ShopSessionHealthReadDto {
  shop_id: string
  platform: 'douyin' | 'pdd'
  platform_shop_id: string
  shop_display_name: string
  status: 'valid'
  version: number
  validated_at: string
  used_cached_validation: boolean
  cookie_updates_applied: number
}

export interface ShopSessionRefreshLeaseReadDto {
  shop_id: string
  lease_id: string
  expected_version: number
  expires_at: string
}
