import {
  type InfiniteData,
  useInfiniteQuery,
  useQuery,
  useQueryClient,
} from '@tanstack/vue-query'
import { computed, type MaybeRefOrGetter, nextTick, ref, toValue } from 'vue'

import type { PageDto } from '@/shared/api'
import { getOnlineRefetchInterval } from '@/shared/utils/query-connectivity'

import type { DeviceReadDto } from '../api/contracts'
import {
  getDevice,
  getDeviceProviderInventories,
  getDevices,
  getDeviceSkillCapabilities,
} from '../api/device-api'

export const DEVICE_CENTER_LIST_PAGE_SIZE = 20
export const DEVICE_FILTER_LIST_PAGE_SIZE = 100
export const DEVICE_LIST_PAGE_SIZE = DEVICE_FILTER_LIST_PAGE_SIZE
export const DEVICE_REFRESH_INTERVAL_MS = 15_000
export const DEVICE_SNAPSHOT_REFRESH_INTERVAL_MS = 60_000

export const deviceQueryKeys = {
  all: ['devices'] as const,
  lists: () => [...deviceQueryKeys.all, 'list'] as const,
  list: (pageSize = DEVICE_FILTER_LIST_PAGE_SIZE) =>
    [...deviceQueryKeys.lists(), { pageSize }] as const,
  detail: (deviceId: string) =>
    [...deviceQueryKeys.all, 'detail', deviceId] as const,
  providerInventories: (deviceId: string) =>
    [...deviceQueryKeys.detail(deviceId), 'provider-inventories'] as const,
  skillCapabilities: (deviceId: string) =>
    [...deviceQueryKeys.detail(deviceId), 'skill-capabilities'] as const,
}

export function getNextDevicePageParam(
  lastPage: PageDto<DeviceReadDto>,
): number | undefined {
  return lastPage.items.length > 0 &&
    lastPage.page * lastPage.page_size < lastPage.total
    ? lastPage.page + 1
    : undefined
}

function useDeviceInfiniteListQuery(
  pageSize: number,
  enabled: MaybeRefOrGetter<boolean>,
  refetchInterval?: number,
) {
  const queryClient = useQueryClient()
  const queryKey = deviceQueryKeys.list(pageSize)
  const manualRefreshing = ref(false)
  const effectiveRefetchInterval = computed(() =>
    manualRefreshing.value || refetchInterval === undefined
      ? false
      : getOnlineRefetchInterval(refetchInterval),
  )
  const query = useInfiniteQuery({
    queryKey,
    enabled: computed(() => toValue(enabled)),
    initialPageParam: 1,
    queryFn: ({ pageParam }) =>
      getDevices({ page: pageParam, page_size: pageSize }),
    getNextPageParam: getNextDevicePageParam,
    staleTime: 30_000,
    refetchInterval: effectiveRefetchInterval,
  })

  async function refreshFromStart(): Promise<void> {
    manualRefreshing.value = true
    await nextTick()
    try {
      await queryClient.cancelQueries({ queryKey, exact: true })
      const firstPage = await getDevices({ page: 1, page_size: pageSize })
      queryClient.setQueryData<InfiniteData<PageDto<DeviceReadDto>, number>>(
        queryKey,
        {
          pages: [firstPage],
          pageParams: [1],
        },
      )
    } finally {
      manualRefreshing.value = false
    }
  }

  return { ...query, refreshFromStart }
}

export function useDeviceListQuery(enabled: MaybeRefOrGetter<boolean> = true) {
  return useDeviceInfiniteListQuery(DEVICE_FILTER_LIST_PAGE_SIZE, enabled)
}

export function useDeviceCenterListQuery(
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  return useDeviceInfiniteListQuery(
    DEVICE_CENTER_LIST_PAGE_SIZE,
    enabled,
    DEVICE_REFRESH_INTERVAL_MS,
  )
}

export function useDeviceDetailQuery(
  deviceId: MaybeRefOrGetter<string | undefined>,
) {
  const refetchInterval = computed(() =>
    getOnlineRefetchInterval(DEVICE_REFRESH_INTERVAL_MS),
  )
  return useQuery({
    queryKey: computed(() => deviceQueryKeys.detail(toValue(deviceId) ?? '')),
    queryFn: () => getDevice(toValue(deviceId) ?? ''),
    enabled: computed(() => Boolean(toValue(deviceId))),
    staleTime: 30_000,
    refetchInterval,
  })
}

export function useDeviceProviderInventoriesQuery(
  deviceId: MaybeRefOrGetter<string | undefined>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  const refetchInterval = computed(() =>
    getOnlineRefetchInterval(DEVICE_SNAPSHOT_REFRESH_INTERVAL_MS),
  )
  return useQuery({
    queryKey: computed(() =>
      deviceQueryKeys.providerInventories(toValue(deviceId) ?? ''),
    ),
    queryFn: () => getDeviceProviderInventories(toValue(deviceId) ?? ''),
    enabled: computed(() => Boolean(toValue(deviceId)) && toValue(enabled)),
    staleTime: 30_000,
    refetchInterval,
  })
}

export function useDeviceSkillCapabilitiesQuery(
  deviceId: MaybeRefOrGetter<string | undefined>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  const refetchInterval = computed(() =>
    getOnlineRefetchInterval(DEVICE_SNAPSHOT_REFRESH_INTERVAL_MS),
  )
  return useQuery({
    queryKey: computed(() =>
      deviceQueryKeys.skillCapabilities(toValue(deviceId) ?? ''),
    ),
    queryFn: () => getDeviceSkillCapabilities(toValue(deviceId) ?? ''),
    enabled: computed(() => Boolean(toValue(deviceId)) && toValue(enabled)),
    staleTime: 30_000,
    refetchInterval,
  })
}
