import type { NotificationChannelType } from '../model/types'

export interface NotificationChannelReadDto {
  channel_id: string
  channel_type: NotificationChannelType
  name: string
  enabled: boolean
  webhook_configured: boolean
  device_offline_enabled: boolean
  device_recovered_enabled: boolean
  created_at: string
  updated_at: string
}

export interface NotificationChannelCreateDto {
  channel_type: NotificationChannelType
  name: string
  enabled: boolean
  webhook_url: string
  device_offline_enabled: boolean
  device_recovered_enabled: boolean
}

export type NotificationChannelUpdateDto = Partial<NotificationChannelCreateDto>

export interface NotificationChannelTestReadDto {
  delivered: boolean
}
