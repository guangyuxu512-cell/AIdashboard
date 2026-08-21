import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'

import type { NotificationChannelSaveInput } from '../model/types'
import { notificationChannelDataSource } from './notification-channel-data-source'

export const notificationChannelQueryKeys = {
  all: ['notification-channels'] as const,
}

export function useNotificationChannelsQuery() {
  return useQuery({
    queryKey: notificationChannelQueryKeys.all,
    queryFn: () => notificationChannelDataSource.list(),
  })
}

export function useCreateNotificationChannelMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: NotificationChannelSaveInput) =>
      notificationChannelDataSource.create(input),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: notificationChannelQueryKeys.all }),
  })
}

export function useUpdateNotificationChannelMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      channelId,
      input,
    }: {
      channelId: string
      input: NotificationChannelSaveInput
    }) => notificationChannelDataSource.update(channelId, input),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: notificationChannelQueryKeys.all }),
  })
}

export function useTestNotificationChannelMutation() {
  return useMutation({
    mutationFn: (channelId: string) => notificationChannelDataSource.test(channelId),
  })
}
