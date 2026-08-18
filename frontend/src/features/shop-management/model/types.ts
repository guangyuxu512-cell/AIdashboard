import type {
  ShopOperationalStatus,
  ShopPlatform,
  ShopSessionStatus,
} from '@/entities/shop'

export interface ShopFilterViewModel {
  platform: ShopPlatform | null
  operationalStatus: ShopOperationalStatus | null
  sessionStatus: ShopSessionStatus | null
  ownerName: string | null
  keyword: string
}

export interface ShopFormViewModel {
  shopName: string
  platform: ShopPlatform | null
  ownerName: string
  executionDeviceId: string | null
  note: string
}

export type ShopFormMode = 'create' | 'edit'
