import { useQueryClient } from '@tanstack/vue-query'
import { computed, nextTick, ref, watch } from 'vue'

import { flattenDevicePages, useDeviceCenterListQuery } from '@/entities/device'
import { taskQueryKeys } from '@/entities/task'
import { classifyInfiniteQueryError } from '@/shared/utils/infinite-query-error'

import {
  summarizeDeviceOverview,
  type DeviceOverviewDataState,
} from './device-overview'
import {
  filterDevicesByQuickFilter,
  getDeviceQuickFilterLabel,
  isDeviceQuickFilterAvailable,
  searchDevicesByDisplayName,
  toggleDeviceMetricFilter,
  type DeviceMetricFilter,
  type DeviceQuickFilter,
} from './device-filter'
import { useDeviceActiveTasks } from './use-device-active-task'

export function useDeviceCenter() {
  const queryClient = useQueryClient()
  const query = useDeviceCenterListQuery()
  const filter = ref<DeviceQuickFilter>('all')
  const searchQuery = ref('')
  const refreshing = ref(false)
  const refreshError = ref<unknown>(null)
  const filterPreparationError = ref<unknown>(null)
  let filterPreparationPromise: Promise<boolean> | null = null
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
  const filterAvailability = computed(() => ({
    all: true,
    online: isDeviceQuickFilterAvailable('online', overview.value),
    running: isDeviceQuickFilterAvailable('running', overview.value),
    offline: isDeviceQuickFilterAvailable('offline', overview.value),
  }))
  const total = computed(() => query.data.value?.pages[0]?.total)
  const hasCompleteDeviceDataset = computed(
    () =>
      query.data.value !== undefined &&
      total.value !== undefined &&
      devices.value.length >= total.value &&
      !query.hasNextPage.value,
  )
  const searchAvailable = computed(() => query.data.value !== undefined)
  const requiresCompleteDeviceDataset = computed(
    () => filter.value !== 'all' || searchQuery.value.trim().length > 0,
  )
  const filterResultReady = computed(
    () =>
      !requiresCompleteDeviceDataset.value ||
      (hasCompleteDeviceDataset.value &&
        (filter.value !== 'running' || overview.value.runningCount !== null)),
  )
  const isFilterPreparing = computed(
    () =>
      requiresCompleteDeviceDataset.value &&
      !filterResultReady.value &&
      filterPreparationError.value === null,
  )
  const filteredDevices = computed(() => {
    if (!filterResultReady.value) return []
    const filtered = filterDevicesByQuickFilter(
      devices.value,
      activeTasks.states.value,
      filter.value,
    )
    return searchDevicesByDisplayName(filtered, searchQuery.value)
  })
  const visibleTotal = computed(() => {
    if (!filterResultReady.value) return undefined
    return filter.value === 'all' && searchQuery.value.trim().length === 0
      ? total.value
      : filteredDevices.value.length
  })
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

  function runningFactsState(): 'pending' | 'ready' | 'error' {
    if (filter.value !== 'running') return 'ready'
    if (overview.value.runningCount !== null) return 'ready'
    if (
      hasCompleteDeviceDataset.value &&
      overview.value.activeUnknownCount > 0 &&
      overview.value.activeUnknownCount ===
        overview.value.activeInitialErrorCount
    ) {
      return 'error'
    }
    return 'pending'
  }

  async function waitForRunningFacts(): Promise<boolean> {
    const initialState = runningFactsState()
    if (initialState !== 'pending') return initialState === 'ready'

    return new Promise<boolean>((resolve) => {
      const stop = watch(
        () => [
          filter.value,
          overview.value.runningCount,
          overview.value.activeUnknownCount,
          overview.value.activeInitialErrorCount,
          hasCompleteDeviceDataset.value,
        ],
        () => {
          const nextState = runningFactsState()
          if (nextState === 'pending') return
          stop()
          resolve(nextState === 'ready')
        },
      )
    })
  }

  async function prepareFilterResults(): Promise<boolean> {
    if (!requiresCompleteDeviceDataset.value || filterResultReady.value) {
      filterPreparationError.value = null
      return true
    }
    if (filterPreparationPromise) return filterPreparationPromise

    filterPreparationError.value = null
    const pending = (async () => {
      try {
        while (query.hasNextPage.value) {
          const result = await query.fetchNextPage({ cancelRefetch: false })
          if (result.isError) throw result.error
          await nextTick()
        }

        if (filter.value === 'running' && !(await waitForRunningFacts())) {
          throw new Error('Active Task facts are incomplete')
        }

        return true
      } catch (error) {
        if (requiresCompleteDeviceDataset.value && !filterResultReady.value) {
          filterPreparationError.value = error
        }
        return false
      }
    })()

    filterPreparationPromise = pending
    const prepared = await pending
    if (filterPreparationPromise === pending) filterPreparationPromise = null
    return prepared
  }

  function setFilter(nextFilter: DeviceQuickFilter): void {
    if (!filterAvailability.value[nextFilter]) return
    filter.value = nextFilter
    filterPreparationError.value = null
    void prepareFilterResults()
  }

  function toggleMetricFilter(metricFilter: DeviceMetricFilter): void {
    const nextFilter = toggleDeviceMetricFilter(filter.value, metricFilter)
    setFilter(nextFilter)
  }

  function setSearchQuery(nextQuery: string): void {
    searchQuery.value = nextQuery
    filterPreparationError.value = null
    void prepareFilterResults()
  }

  async function retryFilterPreparation(): Promise<void> {
    filterPreparationError.value = null
    const retryPromises: Promise<unknown>[] = []
    for (const state of Object.values(activeTasks.states.value)) {
      if (!state.initialError) continue
      const retryResult = state.retry()
      if (retryResult) retryPromises.push(retryResult)
    }
    await Promise.allSettled(retryPromises)
    await nextTick()
    await prepareFilterResults()
  }

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
      return await prepareFilterResults()
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

  watch(
    () => [
      requiresCompleteDeviceDataset.value,
      hasCompleteDeviceDataset.value,
      overview.value.runningCount,
    ],
    () => {
      if (
        requiresCompleteDeviceDataset.value &&
        !filterResultReady.value &&
        filterPreparationError.value === null
      ) {
        void prepareFilterResults()
      }
    },
  )

  return {
    query,
    devices,
    filteredDevices,
    activeTaskStates: activeTasks.states,
    overview,
    filter,
    searchQuery,
    searchAvailable,
    hasCompleteDeviceDataset,
    filterResultReady,
    isFilterPreparing,
    filterPreparationError,
    filterLabel: computed(() => getDeviceQuickFilterLabel(filter.value)),
    filterAvailability,
    visibleTotal,
    setFilter,
    toggleMetricFilter,
    setSearchQuery,
    retryFilterPreparation,
    refreshing,
    total,
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
