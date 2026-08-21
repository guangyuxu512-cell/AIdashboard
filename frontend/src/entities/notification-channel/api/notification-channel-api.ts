import { httpClient } from '@/shared/api'

import type {
  NotificationChannelCreateDto,
  NotificationChannelReadDto,
  NotificationChannelTestReadDto,
  NotificationChannelUpdateDto,
} from './contracts'

const basePath = '/api/v1/notification-channels'

export const notificationChannelApi = {
  async list(): Promise<NotificationChannelReadDto[]> {
    const response = await httpClient.get<NotificationChannelReadDto[]>(basePath)
    return response.data
  },
  async create(
    data: NotificationChannelCreateDto,
  ): Promise<NotificationChannelReadDto> {
    const response = await httpClient.post<NotificationChannelReadDto>(
      basePath,
      data,
    )
    return response.data
  },
  async update(
    channelId: string,
    data: NotificationChannelUpdateDto,
  ): Promise<NotificationChannelReadDto> {
    const response = await httpClient.patch<NotificationChannelReadDto>(
      `${basePath}/${channelId}`,
      data,
    )
    return response.data
  },
  async test(channelId: string): Promise<NotificationChannelTestReadDto> {
    const response = await httpClient.post<NotificationChannelTestReadDto>(
      `${basePath}/${channelId}/test`,
    )
    return response.data
  },
}
