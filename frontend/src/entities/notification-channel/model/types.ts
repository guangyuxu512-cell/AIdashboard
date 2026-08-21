export type NotificationChannelType = 'feishu_webhook' | 'wecom_webhook'

export interface NotificationChannelViewModel {
  channelId: string
  channelType: NotificationChannelType
  name: string
  enabled: boolean
  webhookConfigured: boolean
  deviceOfflineEnabled: boolean
  deviceRecoveredEnabled: boolean
  createdAt: string
  updatedAt: string
}

export interface NotificationChannelSaveInput {
  channelType: NotificationChannelType
  name: string
  enabled: boolean
  webhookUrl: string
  deviceOfflineEnabled: boolean
  deviceRecoveredEnabled: boolean
}

export const NOTIFICATION_CHANNEL_TYPE_OPTIONS = [
  { label: '飞书群机器人', value: 'feishu_webhook' },
  { label: '企业微信群机器人', value: 'wecom_webhook' },
] as const

export function getNotificationChannelTypeLabel(
  type: NotificationChannelType,
): string {
  return (
    NOTIFICATION_CHANNEL_TYPE_OPTIONS.find((option) => option.value === type)
      ?.label ?? type
  )
}
