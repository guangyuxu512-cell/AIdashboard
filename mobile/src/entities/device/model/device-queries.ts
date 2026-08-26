import { useInfiniteQuery, useQuery } from '@tanstack/vue-query'
import { computed, type MaybeRefOrGetter, toValue } from 'vue'

import type { PageDto } from '@/shared/api'

import type { DeviceReadDto } from '../api/contracts'
import { getDevice, getDevices } from '../api/device-api'

export const DEVICE_LIST_PAGE_SIZE = 100

export const deviceQueryKeys = {
  all: ['devices'] as const,
  list: () => [...deviceQueryKeys.all, 'list'] as const,
  detail: (deviceId: string) =>
    [...deviceQueryKeys.all, 'detail', deviceId] as const,
}

export function getNextDevicePageParam(
  lastPage: PageDto<DeviceReadDto>,
): number | undefined {
  return lastPage.items.length > 0 &&
    lastPage.page * lastPage.page_size < lastPage.total
    ? lastPage.page + 1
    : undefined
}

export function useDeviceListQuery(enabled: MaybeRefOrGetter<boolean> = true) {
  return useInfiniteQuery({
    queryKey: deviceQueryKeys.list(),
    enabled: computed(() => toValue(enabled)),
    initialPageParam: 1,
    queryFn: ({ pageParam }) =>
      getDevices({ page: pageParam, page_size: DEVICE_LIST_PAGE_SIZE }),
    getNextPageParam: getNextDevicePageParam,
    staleTime: 30_000,
  })
}

export function useDeviceDetailQuery(
  deviceId: MaybeRefOrGetter<string | undefined>,
) {
  return useQuery({
    queryKey: computed(() => deviceQueryKeys.detail(toValue(deviceId) ?? '')),
    queryFn: () => getDevice(toValue(deviceId) ?? ''),
    enabled: computed(() => Boolean(toValue(deviceId))),
    staleTime: 30_000,
  })
}
