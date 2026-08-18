import type {
  ShopEnabledStatus,
  ShopPlatform,
  ShopSessionStatus,
} from '@/entities/shop'

export interface ShopFilterViewModel {
  platform: ShopPlatform | null
  enabledStatus: ShopEnabledStatus | null
  sessionStatus: ShopSessionStatus | null
  ownerUserId: string | null
  keyword: string
}

export interface ShopFormViewModel {
  shopName: string
  platform: ShopPlatform | null
  enabled: boolean
  ownerUserId: string | null
  note: string
}

export type ShopFormMode = 'create' | 'edit'
