export type BackendShopPlatform = 'douyin' | 'pdd'
export type ShopSessionStatusDto =
  | 'not_configured'
  | 'captured'
  | 'valid'
  | 'invalid'
  | 'refresh_required'

export interface ShopReadDto {
  shop_id: string
  display_name: string
  platform: BackendShopPlatform
  platform_shop_id: string | null
  enabled: boolean
  owner_user_id: string | null
  note: string | null
  deleted_at: string | null
  created_at: string
  updated_at: string
}

export interface ShopListReadDto extends ShopReadDto {
  session_status: ShopSessionStatusDto | null
}

export interface ShopCreateDto {
  display_name: string
  platform: BackendShopPlatform
  enabled?: boolean
  owner_user_id?: string | null
  note?: string | null
}

export interface ShopUpdateDto {
  display_name?: string
  platform?: BackendShopPlatform
  enabled?: boolean
  owner_user_id?: string | null
  note?: string | null
}

export interface ShopDeviceBindingReadDto {
  shop_id: string
  device_id: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface ShopDeviceBindingCreateDto {
  device_id: string
  enabled: boolean
}

export interface ShopDeviceBindingUpdateDto {
  enabled?: boolean
}
