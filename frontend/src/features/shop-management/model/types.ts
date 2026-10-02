import type { ShopEnabledStatus, ShopPlatform } from '@/entities/shop'

export interface ShopFilterViewModel {
  enabledStatus: ShopEnabledStatus | null
  ownerUserId: string | null
  keyword: string
}

export interface ShopFormViewModel {
  shopName: string
  platform: ShopPlatform | null
  platformShopId: string | null
  enabled: boolean
  ownerUserId: string | null
  note: string
}

export type ShopFormMode = 'create' | 'edit'
