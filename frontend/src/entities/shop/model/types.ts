export type ShopPlatform = 'douyin' | 'taobao' | 'pdd' | 'jd'

export type ShopOperationalStatus = 'normal' | 'attention' | 'disabled'

export type ShopSessionStatus = 'normal' | 'warning' | 'not_configured'

export type ShopAutomationStatus = 'running' | 'idle' | 'paused'

export type ShopConfigurationStatus = 'configured' | 'not_configured'

/**
 * 店铺中心第一版的前端展示模型。
 *
 * 该类型只服务本地 Fixture 与 UI 验证，不是 Backend DTO，也不约束未来数据库字段。
 */
export interface ShopListItemViewModel {
  shopId: string
  shopName: string
  platform: ShopPlatform
  ownerName: string
  operationalStatus: ShopOperationalStatus
  sessionStatus: ShopSessionStatus
  executionDeviceId: string | null
  executionDeviceName: string | null
  automationStatus: ShopAutomationStatus
  todayGmvDisplay: string
  updatedAtDisplay: string
  accountConfigurationStatus: ShopConfigurationStatus
  sessionConfigurationStatus: ShopConfigurationStatus
  note: string
}
