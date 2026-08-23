import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/vue-query'
import { computed, toValue, type MaybeRefOrGetter } from 'vue'

import type { DeviceSaveInput } from '../model/types'
import { getYingdaoInventory } from './device-provider-data-source'
import { getDeviceSkillCapabilities } from './device-skill-capability-data-source'
import { deviceDataSource, type DeviceListParams } from './device-data-source'
import { deviceApi } from './device-api'

export const deviceQueryKeys = {
  all: ['devices'] as const,
  list: (params: DeviceListParams) => ['devices', 'list', params] as const,
  detail: (deviceId: string | null) => ['devices', 'detail', deviceId] as const,
  providerInventories: (deviceId: string | null) =>
    ['devices', 'provider-inventories', deviceId] as const,
  skillCapabilities: (deviceId: string | null) =>
    ['devices', 'skill-capabilities', deviceId] as const,
  workerCredential: (deviceId: string | null) =>
    ['devices', 'worker-credential', deviceId] as const,
}

export function useDeviceWorkerCredentialQuery(
  deviceId: MaybeRefOrGetter<string | null>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  return useQuery({
    queryKey: computed(() =>
      deviceQueryKeys.workerCredential(toValue(deviceId)),
    ),
    queryFn: () => deviceApi.getWorkerCredential(toValue(deviceId)!),
    enabled: computed(
      () => Boolean(toValue(deviceId)) && Boolean(toValue(enabled)),
    ),
  })
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

export function useDeviceSkillCapabilitiesQuery(
  deviceId: MaybeRefOrGetter<string | null>,
) {
  return useQuery({
    queryKey: computed(() =>
      deviceQueryKeys.skillCapabilities(toValue(deviceId)),
    ),
    queryFn: () => getDeviceSkillCapabilities(toValue(deviceId)!),
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
    placeholderData: keepPreviousData,
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

export function useSetDeviceEnabledMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ deviceId, enabled }: { deviceId: string; enabled: boolean }) =>
      deviceDataSource.setEnabled(deviceId, enabled),
    onSuccess: (_, variables) =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: deviceQueryKeys.all }),
        queryClient.invalidateQueries({
          queryKey: deviceQueryKeys.detail(variables.deviceId),
        }),
      ]),
  })
}

export function useRemoveDeviceMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (deviceId: string) => deviceDataSource.remove(deviceId),
    onSuccess: (_, deviceId) => {
      queryClient.removeQueries({ queryKey: deviceQueryKeys.detail(deviceId) })
      return queryClient.invalidateQueries({ queryKey: deviceQueryKeys.all })
    },
  })
}
