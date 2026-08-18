export type ShopPlatform = 'douyin' | 'taobao' | 'pdd' | 'jd'

export type ShopEnabledStatus = 'enabled' | 'disabled'

export type ShopSessionStatus =
  'normal' | 'warning' | 'not_configured' | 'unavailable'

export type ShopAutomationStatus = 'running' | 'idle' | 'paused' | 'unavailable'

export type ShopConfigurationStatus =
  'configured' | 'not_configured' | 'unavailable'

/**
 * 店铺中心第一版的前端展示模型。
 *
 * 该类型只服务本地 Fixture 与 UI 验证，不是 Backend DTO，也不约束未来数据库字段。
 */
export interface ShopListItemViewModel {
  shopId: string
  shopName: string
  platform: ShopPlatform
  ownerUserId: string | null
  ownerName: string
  enabled: boolean
  enabledStatus: ShopEnabledStatus
  sessionStatus: ShopSessionStatus
  executionDeviceId: string | null
  executionDeviceName: string | null
  backupDeviceNames: string[]
  automationStatus: ShopAutomationStatus
  todayGmvDisplay: string
  updatedAtDisplay: string
  accountConfigurationStatus: ShopConfigurationStatus
  sessionConfigurationStatus: ShopConfigurationStatus
  note: string
  dataSource: 'mock' | 'real'
}

export interface ShopListFilters {
  platform: ShopPlatform | null
  enabledStatus: ShopEnabledStatus | null
  sessionStatus: ShopSessionStatus | null
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
