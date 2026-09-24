import type { PlatformCode } from '@/entities/platform'

/** Shop API 当前正式支持的平台子集。 */
export type ShopPlatform = Extract<PlatformCode, 'douyin' | 'pdd'>

/** 店铺中心平台栏的前端展示值，不是 Backend 平台枚举。 */
export type ShopPlatformFilter = 'all' | PlatformCode

export type ShopEnabledStatus = 'enabled' | 'disabled'
export type ShopLoginStatus =
  | 'not_configured'
  | 'captured'
  | 'valid'
  | 'invalid'
  | 'refresh_required'
export interface ShopDeviceBindingViewModel {
  deviceId: string
  deviceName: string
  enabled: boolean
}

/**
 * 店铺中心的前端展示模型。
 *
 * 该类型由真实 DTO 显式映射，也用于本地 Fixture；它不是 Backend DTO 或数据库模型。
 */
export interface ShopListItemViewModel {
  shopId: string
  shopName: string
  platform: ShopPlatform
  platformShopId?: string | null
  ownerUserId: string | null
  ownerName: string
  enabled: boolean
  enabledStatus: ShopEnabledStatus
  loginStatus: ShopLoginStatus
  executionDeviceIds: string[]
  executionDeviceNames: string[]
  deviceBindings?: ShopDeviceBindingViewModel[]
  createdAtDisplay: string
  updatedAtDisplay: string
  note: string
  /** A manager-confirmed coverage boundary, not the CC onboarding date. */
  operatingStartDate?: string | null
  dataSource: 'mock' | 'real'
}

export interface ShopListFilters {
  enabledStatus: ShopEnabledStatus | null
  ownerUserId: string | null
  keyword: string
}

export interface ShopSaveInput {
  shopName: string
  platform: ShopPlatform
  platformShopId?: string | null
  enabled: boolean
  ownerUserId: string | null
  note: string
  /** Omitted on create; an explicit null clears the confirmed boundary. */
  operatingStartDate?: string | null
}

export interface ShopDeviceBindingInput {
  deviceId: string
  enabled: boolean
}

export interface ShopSelectOption {
  [key: string]: unknown
  label: string
  value: string
  disabled?: boolean
}
