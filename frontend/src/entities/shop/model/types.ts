export type ShopPlatform = 'douyin' | 'pdd'

export type ShopPlatformFilter = 'all' | ShopPlatform

export type ShopEnabledStatus = 'enabled' | 'disabled'

/**
 * 店铺中心的前端展示模型。
 *
 * 该类型由真实 DTO 显式映射，也用于本地 Fixture；它不是 Backend DTO 或数据库模型。
 */
export interface ShopListItemViewModel {
  shopId: string
  shopName: string
  platform: ShopPlatform
  ownerUserId: string | null
  ownerName: string
  enabled: boolean
  enabledStatus: ShopEnabledStatus
  executionDeviceId: string | null
  executionDeviceName: string | null
  backupDeviceNames: string[]
  createdAtDisplay: string
  updatedAtDisplay: string
  note: string
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
  enabled: boolean
  ownerUserId: string | null
  note: string
}

export interface ShopSelectOption {
  [key: string]: unknown
  label: string
  value: string
}
