import { useQueryClient } from '@tanstack/vue-query'
import { computed, ref, watch } from 'vue'

import { flattenDevicePages, useDeviceCenterListQuery } from '@/entities/device'
import { taskQueryKeys } from '@/entities/task'
import { classifyInfiniteQueryError } from '@/shared/utils/infinite-query-error'

import {
  summarizeDeviceOverview,
  type DeviceOverviewDataState,
} from './device-overview'
import { useDeviceActiveTasks } from './use-device-active-task'

export function useDeviceCenter() {
  const queryClient = useQueryClient()
  const query = useDeviceCenterListQuery()
  const refreshing = ref(false)
  const refreshError = ref<unknown>(null)
  const devices = computed(() =>
    flattenDevicePages(query.data.value?.pages ?? []),
  )
  const activeTasks = useDeviceActiveTasks(() =>
    devices.value.map((device) => device.deviceId),
  )
  const deviceDataState = computed<DeviceOverviewDataState>(() => {
    if (query.data.value !== undefined) return 'ready'
    if (query.isError.value || refreshError.value !== null) return 'error'
    return 'loading'
  })
  const overview = computed(() =>
    summarizeDeviceOverview(
      devices.value,
      activeTasks.states.value,
      deviceDataState.value,
      query.data.value?.pages[0]?.total ?? devices.value.length,
    ),
  )
  const errorKind = computed(() =>
    refreshError.value
      ? query.data.value === undefined
        ? 'initial'
        : 'background'
      : classifyInfiniteQueryError({
          hasSuccessfulData: query.data.value !== undefined,
          isError: query.isError.value,
          isFetchNextPageError: query.isFetchNextPageError.value,
        }),
  )
  watch(query.dataUpdatedAt, () => {
    refreshError.value = null
  })

  async function refresh(): Promise<boolean> {
    refreshing.value = true
    refreshError.value = null
    try {
      await query.refreshFromStart()
      void queryClient
        .refetchQueries({
          queryKey: taskQueryKeys.activeAll(),
          type: 'active',
        })
        .catch(() => undefined)
      return true
    } catch (error) {
      refreshError.value = error
      return false
    } finally {
      refreshing.value = false
    }
  }

  async function loadMore(): Promise<void> {
    if (
      refreshing.value ||
      !query.hasNextPage.value ||
      query.isFetchingNextPage.value ||
      errorKind.value === 'next-page'
    ) {
      return
    }
    await query.fetchNextPage()
  }

  async function retryLoadMore(): Promise<void> {
    if (
      refreshing.value ||
      !query.hasNextPage.value ||
      query.isFetchingNextPage.value
    ) {
      return
    }
    await query.fetchNextPage()
  }

  return {
    query,
    devices,
    activeTaskStates: activeTasks.states,
    overview,
    refreshing,
    total: computed(() => query.data.value?.pages[0]?.total),
    errorKind,
    isInitialLoading: computed(
      () => query.isLoading.value && query.data.value === undefined,
    ),
    isInitialError: computed(() => errorKind.value === 'initial'),
    isBackgroundError: computed(() => errorKind.value === 'background'),
    isNextPageError: computed(() => errorKind.value === 'next-page'),
    refresh,
    loadMore,
    retryLoadMore,
  }
}
