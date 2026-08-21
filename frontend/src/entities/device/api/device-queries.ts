import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, toValue, type MaybeRefOrGetter } from 'vue'

import type { DeviceSaveInput } from '../model/types'
import { getYingdaoInventory } from './device-provider-data-source'
import { deviceDataSource, type DeviceListParams } from './device-data-source'

export const deviceQueryKeys = {
  all: ['devices'] as const,
  list: (params: DeviceListParams) => ['devices', 'list', params] as const,
  detail: (deviceId: string | null) => ['devices', 'detail', deviceId] as const,
  providerInventories: (deviceId: string | null) =>
    ['devices', 'provider-inventories', deviceId] as const,
}

export function useDeviceProviderInventoriesQuery(
  deviceId: MaybeRefOrGetter<string | null>,
) {
  return useQuery({
    queryKey: computed(() =>
      deviceQueryKeys.providerInventories(toValue(deviceId)),
    ),
    queryFn: () => getYingdaoInventory(toValue(deviceId)!),
    enabled: computed(() => Boolean(toValue(deviceId))),
  })
}

export function useDeviceListQuery(
  params: MaybeRefOrGetter<DeviceListParams>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  return useQuery({
    queryKey: computed(() => deviceQueryKeys.list(toValue(params))),
    queryFn: () => deviceDataSource.list(toValue(params)),
    enabled: computed(() => toValue(enabled)),
    refetchInterval: deviceDataSource.mode === 'real' ? 15_000 : false,
  })
}

export function useDeviceDetailQuery(
  deviceId: MaybeRefOrGetter<string | null>,
) {
  return useQuery({
    queryKey: computed(() => deviceQueryKeys.detail(toValue(deviceId))),
    queryFn: () => deviceDataSource.get(toValue(deviceId)!),
    enabled: computed(() => Boolean(toValue(deviceId))),
    refetchInterval: deviceDataSource.mode === 'real' ? 15_000 : false,
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
