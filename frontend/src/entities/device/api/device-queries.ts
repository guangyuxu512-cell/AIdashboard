import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, toValue, type MaybeRefOrGetter } from 'vue'

import type { DeviceSaveInput } from '../model/types'
import { apiMode } from '@/shared/api'
import { deviceApi } from './device-api'
import { mapYingdaoInventoryDto } from './device-mapper'
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
    queryFn: async () => {
      const inventories = await deviceApi.getProviderInventories(
        toValue(deviceId)!,
      )
      const yingdao = inventories.find(
        (inventory) => inventory.provider_code === 'yingdao',
      )
      return yingdao ? mapYingdaoInventoryDto(yingdao) : null
    },
    enabled: computed(() => apiMode === 'real' && Boolean(toValue(deviceId))),
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
