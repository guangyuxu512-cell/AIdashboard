import { useQueryClient } from '@tanstack/vue-query'
import { computed, ref, watch } from 'vue'

import { flattenDevicePages, useDeviceCenterListQuery } from '@/entities/device'
import { taskQueryKeys } from '@/entities/task'
import { classifyInfiniteQueryError } from '@/shared/utils/infinite-query-error'

export function useDeviceCenter() {
  const queryClient = useQueryClient()
  const query = useDeviceCenterListQuery()
  const refreshing = ref(false)
  const refreshError = ref<unknown>(null)
  const devices = computed(() =>
    flattenDevicePages(query.data.value?.pages ?? []),
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
  const errorMessage = computed(() => {
    const error = refreshError.value ?? query.error.value
    return error instanceof Error ? error.message : '设备加载失败，请稍后重试'
  })

  watch(query.dataUpdatedAt, () => {
    refreshError.value = null
  })

  async function refresh(): Promise<void> {
    refreshing.value = true
    refreshError.value = null
    try {
      const [deviceRefresh] = await Promise.allSettled([
        query.refreshFromStart(),
        queryClient.refetchQueries({
          queryKey: taskQueryKeys.activeAll(),
          type: 'active',
        }),
      ])
      if (deviceRefresh?.status === 'rejected') {
        refreshError.value = deviceRefresh.reason
      }
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
    refreshing,
    total: computed(() => query.data.value?.pages[0]?.total),
    errorKind,
    errorMessage,
    isInitialLoading: computed(
      () => query.isPending.value && query.data.value === undefined,
    ),
    isInitialError: computed(() => errorKind.value === 'initial'),
    isBackgroundError: computed(() => errorKind.value === 'background'),
    isNextPageError: computed(() => errorKind.value === 'next-page'),
    refresh,
    loadMore,
    retryLoadMore,
  }
}
