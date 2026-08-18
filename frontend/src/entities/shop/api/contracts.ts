export type BackendShopPlatform = 'douyin' | 'pdd'
export type BindingRoleDto = 'primary' | 'backup'

export interface ShopReadDto {
  shop_id: string
  display_name: string
  platform: BackendShopPlatform
  enabled: boolean
  owner_user_id: string | null
  note: string | null
  created_at: string
  updated_at: string
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
  binding_role: BindingRoleDto
  enabled: boolean
  created_at: string
  updated_at: string
}
