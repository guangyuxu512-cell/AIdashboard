import { computed, ref, watch } from 'vue'

import {
  flattenTaskPages,
  type TaskListFilters,
  type TaskListItem,
  type TaskStatusDto,
  useTaskListQuery,
  useTaskTotalQuery,
} from '@/entities/task'
import { classifyInfiniteQueryError } from '@/shared/utils/infinite-query-error'

import {
  buildTaskBaseFilters,
  formatTaskDateFilterLabel,
  getTaskStatusFilterOption,
  createDefaultTaskFilterDraft,
  type TaskFilterDraft,
  type TaskStatusFilter,
} from './task-filter'

type TaskQuery = ReturnType<typeof useTaskListQuery>

function queryErrorKind(query: TaskQuery) {
  return classifyInfiniteQueryError({
    hasSuccessfulData: query.data.value !== undefined,
    isError: query.isError.value,
    isFetchNextPageError: query.isFetchNextPageError.value,
  })
}

function backendStatusForFilter(
  filter: TaskStatusFilter,
): TaskStatusDto | undefined {
  if (filter === 'completed') return 'success'
  if (filter === 'exception') return 'failed'
  if (filter === 'running' || filter === 'pending') return filter
  return undefined
}

function mergeTaskStreams(
  primary: TaskListItem[],
  secondary: TaskListItem[],
): TaskListItem[] {
  const tasks = new Map<string, TaskListItem>()
  for (const task of [...primary, ...secondary]) tasks.set(task.taskId, task)
  return [...tasks.values()].sort((left, right) => {
    const timeOrder =
      new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime()
    return timeOrder || right.taskId.localeCompare(left.taskId)
  })
}

export function useTaskCenter() {
  const status = ref<TaskStatusFilter>('all')
  const appliedFilters = ref<TaskFilterDraft>(createDefaultTaskFilterDraft())
  const refreshing = ref(false)
  const refreshError = ref<unknown>(null)

  const baseFilters = computed(() => buildTaskBaseFilters(appliedFilters.value))
  const requestFilters = computed<TaskListFilters>(() => {
    const backendStatus = backendStatusForFilter(status.value)
    return {
      ...baseFilters.value,
      ...(backendStatus ? { status: backendStatus } : {}),
    }
  })
  const lostRequestFilters = computed<TaskListFilters>(() => ({
    ...baseFilters.value,
    status: 'lost',
  }))
  const exceptionSelected = computed(() => status.value === 'exception')
  const query = useTaskListQuery(requestFilters)
  const lostQuery = useTaskListQuery(lostRequestFilters, exceptionSelected)

  const runningTotalQuery = useTaskTotalQuery(
    computed(() => ({ ...baseFilters.value, status: 'running' })),
  )
  const pendingTotalQuery = useTaskTotalQuery(
    computed(() => ({ ...baseFilters.value, status: 'pending' })),
  )
  const failedTotalQuery = useTaskTotalQuery(
    computed(() => ({ ...baseFilters.value, status: 'failed' })),
  )
  const lostTotalQuery = useTaskTotalQuery(
    computed(() => ({ ...baseFilters.value, status: 'lost' })),
  )
  const successTotalQuery = useTaskTotalQuery(
    computed(() => ({ ...baseFilters.value, status: 'success' })),
  )
  const metricQueries = [
    runningTotalQuery,
    pendingTotalQuery,
    failedTotalQuery,
    lostTotalQuery,
    successTotalQuery,
  ] as const

  const primaryTasks = computed(() =>
    flattenTaskPages(query.data.value?.pages ?? []),
  )
  const lostTasks = computed(() =>
    flattenTaskPages(lostQuery.data.value?.pages ?? []),
  )
  const tasks = computed(() =>
    exceptionSelected.value
      ? mergeTaskStreams(primaryTasks.value, lostTasks.value)
      : primaryTasks.value,
  )
  const currentTotal = computed<number | null>(() => {
    const primaryTotal = query.data.value?.pages[0]?.total
    if (primaryTotal === undefined) return null
    if (!exceptionSelected.value) return primaryTotal
    const lostTotal = lostQuery.data.value?.pages[0]?.total
    return lostTotal === undefined ? null : primaryTotal + lostTotal
  })
  const metricTotals = computed(() => {
    const failed = failedTotalQuery.data.value
    const lost = lostTotalQuery.data.value
    return {
      running: runningTotalQuery.data.value ?? null,
      pending: pendingTotalQuery.data.value ?? null,
      exception:
        failed === undefined || lost === undefined ? null : failed + lost,
      completed: successTotalQuery.data.value ?? null,
    }
  })
  const metricsBusy = computed(() =>
    metricQueries.some((metricQuery) => metricQuery.isLoading.value),
  )
  const metricsUnavailable = computed(() =>
    metricQueries.some(
      (metricQuery) =>
        metricQuery.data.value === undefined && metricQuery.isError.value,
    ),
  )
  const hasCompleteListData = computed(
    () =>
      query.data.value !== undefined &&
      (!exceptionSelected.value || lostQuery.data.value !== undefined),
  )
  const errorKind = computed(() => {
    if (refreshError.value) {
      return hasCompleteListData.value ? 'background' : 'initial'
    }
    const primaryKind = queryErrorKind(query)
    const secondaryKind = exceptionSelected.value
      ? queryErrorKind(lostQuery)
      : null
    if (primaryKind === 'next-page' || secondaryKind === 'next-page') {
      return 'next-page'
    }
    if (primaryKind === 'initial' || secondaryKind === 'initial') {
      return 'initial'
    }
    if (primaryKind === 'background' || secondaryKind === 'background') {
      return 'background'
    }
    return null
  })

  watch([query.dataUpdatedAt, lostQuery.dataUpdatedAt], () => {
    refreshError.value = null
  })

  const searchQuery = computed({
    get: () => appliedFilters.value.search,
    set: (search: string) => {
      appliedFilters.value = { ...appliedFilters.value, search }
    },
  })
  const dateLabel = computed(() =>
    formatTaskDateFilterLabel(appliedFilters.value),
  )
  const resultLabel = computed(
    () => getTaskStatusFilterOption(status.value).label,
  )
  const emptyDescription = computed(() => {
    if (searchQuery.value.trim()) return '未找到相关任务'
    if (status.value === 'exception') return '暂无异常任务'
    if (appliedFilters.value.datePreset === 'last-7-days') {
      return '近7天无任务'
    }
    return '当前条件无任务'
  })

  function toggleStatus(nextStatus: Exclude<TaskStatusFilter, 'all'>): void {
    status.value = status.value === nextStatus ? 'all' : nextStatus
  }

  function clearStatus(): void {
    status.value = 'all'
  }

  function applyFilters(nextFilters: TaskFilterDraft): void {
    appliedFilters.value = {
      ...nextFilters,
      dateRange: [nextFilters.dateRange[0], nextFilters.dateRange[1]],
    }
  }

  async function refresh(): Promise<boolean> {
    refreshing.value = true
    refreshError.value = null
    try {
      const listRefreshes = [query.refreshFromStart()]
      if (exceptionSelected.value) {
        listRefreshes.push(lostQuery.refreshFromStart())
      }
      await Promise.all(listRefreshes)
      void Promise.allSettled(
        metricQueries.map((metricQuery) => metricQuery.refetch()),
      )
      return true
    } catch (error) {
      refreshError.value = error
      return false
    } finally {
      refreshing.value = false
    }
  }

  async function retry(): Promise<void> {
    const requests: Promise<unknown>[] = [query.refetch()]
    if (exceptionSelected.value) requests.push(lostQuery.refetch())
    await Promise.all(requests)
  }

  async function loadMore(): Promise<void> {
    if (refreshing.value || errorKind.value === 'next-page') return
    const requests: Promise<unknown>[] = []
    if (query.hasNextPage.value && !query.isFetchingNextPage.value) {
      requests.push(query.fetchNextPage())
    }
    if (
      exceptionSelected.value &&
      lostQuery.hasNextPage.value &&
      !lostQuery.isFetchingNextPage.value
    ) {
      requests.push(lostQuery.fetchNextPage())
    }
    await Promise.all(requests)
  }

  async function retryLoadMore(): Promise<void> {
    const requests: Promise<unknown>[] = []
    if (query.hasNextPage.value && !query.isFetchingNextPage.value) {
      requests.push(query.fetchNextPage())
    }
    if (
      exceptionSelected.value &&
      lostQuery.hasNextPage.value &&
      !lostQuery.isFetchingNextPage.value
    ) {
      requests.push(lostQuery.fetchNextPage())
    }
    await Promise.all(requests)
  }

  return {
    status,
    appliedFilters,
    baseFilters,
    requestFilters,
    query,
    lostQuery,
    tasks,
    currentTotal,
    metricTotals,
    metricsBusy,
    metricsUnavailable,
    searchQuery,
    dateLabel,
    resultLabel,
    emptyDescription,
    refreshing,
    isInitialLoading: computed(
      () =>
        !hasCompleteListData.value &&
        (query.isLoading.value ||
          (exceptionSelected.value && lostQuery.isLoading.value)),
    ),
    errorKind,
    isInitialError: computed(() => errorKind.value === 'initial'),
    isBackgroundError: computed(() => errorKind.value === 'background'),
    isNextPageError: computed(() => errorKind.value === 'next-page'),
    isFetchingNextPage: computed(
      () =>
        query.isFetchingNextPage.value ||
        (exceptionSelected.value && lostQuery.isFetchingNextPage.value),
    ),
    hasNextPage: computed(
      () =>
        Boolean(query.hasNextPage.value) ||
        (exceptionSelected.value && Boolean(lostQuery.hasNextPage.value)),
    ),
    toggleStatus,
    clearStatus,
    applyFilters,
    retry,
    refresh,
    loadMore,
    retryLoadMore,
  }
}
