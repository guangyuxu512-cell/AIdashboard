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
  /** Naive UI epoch timestamp; converted to a Shanghai calendar date on save. */
  operatingStartDate: number | null
}

export type ShopFormMode = 'create' | 'edit'
