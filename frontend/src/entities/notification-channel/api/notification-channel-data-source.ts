import { apiMode, type ApiMode } from '@/shared/api'

import type {
  NotificationChannelSaveInput,
  NotificationChannelViewModel,
} from '../model/types'
import type {
  NotificationChannelCreateDto,
  NotificationChannelReadDto,
  NotificationChannelUpdateDto,
} from './contracts'
import { notificationChannelApi } from './notification-channel-api'

export interface NotificationChannelDataSource {
  readonly mode: ApiMode
  list(): Promise<NotificationChannelViewModel[]>
  create(input: NotificationChannelSaveInput): Promise<NotificationChannelViewModel>
  update(
    channelId: string,
    input: NotificationChannelSaveInput,
  ): Promise<NotificationChannelViewModel>
  test(channelId: string): Promise<void>
}

function mapRead(dto: NotificationChannelReadDto): NotificationChannelViewModel {
  return {
    channelId: dto.channel_id,
    channelType: dto.channel_type,
    name: dto.name,
    enabled: dto.enabled,
    webhookConfigured: dto.webhook_configured,
    deviceOfflineEnabled: dto.device_offline_enabled,
    deviceRecoveredEnabled: dto.device_recovered_enabled,
    createdAt: dto.created_at,
    updatedAt: dto.updated_at,
  }
}

function mapCreate(input: NotificationChannelSaveInput): NotificationChannelCreateDto {
  return {
    channel_type: input.channelType,
    name: input.name.trim(),
    enabled: input.enabled,
    webhook_url: input.webhookUrl.trim(),
    device_offline_enabled: input.deviceOfflineEnabled,
    device_recovered_enabled: input.deviceRecoveredEnabled,
  }
}

function mapUpdate(input: NotificationChannelSaveInput): NotificationChannelUpdateDto {
  return mapCreate(input)
}

export function createMockNotificationChannelDataSource(): NotificationChannelDataSource {
  const rows: NotificationChannelViewModel[] = []
  let sequence = 1
  return {
    mode: 'mock',
    async list() {
      return rows.map((row) => ({ ...row }))
    },
    async create(input) {
      if (!input.webhookUrl.trim()) throw new Error('首次配置必须填写 Webhook URL')
      const now = new Date().toISOString()
      const row: NotificationChannelViewModel = {
        channelId: `notification-fixture-${sequence++}`,
        channelType: input.channelType,
        name: input.name.trim(),
        enabled: input.enabled,
        webhookConfigured: true,
        deviceOfflineEnabled: input.deviceOfflineEnabled,
        deviceRecoveredEnabled: input.deviceRecoveredEnabled,
        createdAt: now,
        updatedAt: now,
      }
      rows.push(row)
      return { ...row }
    },
    async update(channelId, input) {
      const index = rows.findIndex((row) => row.channelId === channelId)
      if (index < 0) throw new Error('通知通道不存在')
      const current = rows[index]!
      const updated: NotificationChannelViewModel = {
        ...current,
        channelType: input.channelType,
        name: input.name.trim(),
        enabled: input.enabled,
        webhookConfigured: current.webhookConfigured || Boolean(input.webhookUrl.trim()),
        deviceOfflineEnabled: input.deviceOfflineEnabled,
        deviceRecoveredEnabled: input.deviceRecoveredEnabled,
        updatedAt: new Date().toISOString(),
      }
      rows[index] = updated
      return { ...updated }
    },
    async test(channelId) {
      if (!rows.some((row) => row.channelId === channelId)) {
        throw new Error('通知通道不存在')
      }
    },
  }
}

const realNotificationChannelDataSource: NotificationChannelDataSource = {
  mode: 'real',
  async list() {
    return (await notificationChannelApi.list()).map(mapRead)
  },
  async create(input) {
    return mapRead(await notificationChannelApi.create(mapCreate(input)))
  },
  async update(channelId, input) {
    return mapRead(
      await notificationChannelApi.update(channelId, mapUpdate(input)),
    )
  },
  async test(channelId) {
    await notificationChannelApi.test(channelId)
  },
}

export function createNotificationChannelDataSource(
  mode: ApiMode,
): NotificationChannelDataSource {
  return mode === 'real'
    ? realNotificationChannelDataSource
    : createMockNotificationChannelDataSource()
}

export const notificationChannelDataSource =
  createNotificationChannelDataSource(apiMode)
