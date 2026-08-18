import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, toValue, type MaybeRefOrGetter } from 'vue'

import type { DeviceSaveInput } from '../model/types'
import { deviceDataSource, type DeviceListParams } from './device-data-source'

export const deviceQueryKeys = {
  all: ['devices'] as const,
  list: (params: DeviceListParams) => ['devices', 'list', params] as const,
  detail: (deviceId: string | null) => ['devices', 'detail', deviceId] as const,
}

export function useDeviceListQuery(params: MaybeRefOrGetter<DeviceListParams>) {
  return useQuery({
    queryKey: computed(() => deviceQueryKeys.list(toValue(params))),
    queryFn: () => deviceDataSource.list(toValue(params)),
  })
}

export function useDeviceDetailQuery(
  deviceId: MaybeRefOrGetter<string | null>,
) {
  return useQuery({
    queryKey: computed(() => deviceQueryKeys.detail(toValue(deviceId))),
    queryFn: () => deviceDataSource.get(toValue(deviceId)!),
    enabled: computed(() => Boolean(toValue(deviceId))),
  })
}

export function useCreateDeviceMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: DeviceSaveInput) => deviceDataSource.create(input),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: deviceQueryKeys.all }),
  })
}

export function useUpdateDeviceMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      deviceId,
      input,
    }: {
      deviceId: string
      input: DeviceSaveInput
    }) => deviceDataSource.update(deviceId, input),
    onSuccess: (_, variables) =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: deviceQueryKeys.all }),
        queryClient.invalidateQueries({
          queryKey: deviceQueryKeys.detail(variables.deviceId),
        }),
      ]),
  })
}
