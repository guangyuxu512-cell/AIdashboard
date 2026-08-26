import { computed, ref } from 'vue'

import {
  flattenTaskPages,
  type TaskStatusDto,
  useTaskListQuery,
} from '@/entities/task'
import { classifyInfiniteQueryError } from '@/shared/utils/infinite-query-error'

import {
  buildTaskListFilters,
  createDefaultTaskFilterDraft,
  type TaskFilterDraft,
  type TaskStatusFilter,
} from './task-filter'

export function useTaskCenter() {
  const status = ref<TaskStatusFilter>('all')
  const appliedFilters = ref<TaskFilterDraft>(createDefaultTaskFilterDraft())
  const refreshing = ref(false)
  const requestFilters = computed(() =>
    buildTaskListFilters(status.value, appliedFilters.value),
  )
  const query = useTaskListQuery(requestFilters)

  const tasks = computed(() => flattenTaskPages(query.data.value?.pages ?? []))
  const errorKind = computed(() =>
    classifyInfiniteQueryError({
      hasSuccessfulData: query.data.value !== undefined,
      isError: query.isError.value,
      isFetchNextPageError: query.isFetchNextPageError.value,
    }),
  )
  const errorMessage = computed(() => {
    const error = query.error.value
    return error instanceof Error ? error.message : '任务加载失败，请稍后重试'
  })

  function setStatus(nextStatus: TaskStatusDto | 'all'): void {
    status.value = nextStatus
  }

  function applyFilters(nextFilters: TaskFilterDraft): void {
    appliedFilters.value = {
      ...nextFilters,
      dateRange: [nextFilters.dateRange[0], nextFilters.dateRange[1]],
    }
  }

  async function refresh(): Promise<void> {
    refreshing.value = true
    try {
      await query.refreshFromStart()
    } finally {
      refreshing.value = false
    }
  }

  async function loadMore(): Promise<void> {
    if (
      !query.hasNextPage.value ||
      query.isFetchingNextPage.value ||
      errorKind.value === 'next-page'
    ) {
      return
    }
    await query.fetchNextPage()
  }

  async function retryLoadMore(): Promise<void> {
    if (!query.hasNextPage.value || query.isFetchingNextPage.value) return
    await query.fetchNextPage()
  }

  return {
    status,
    appliedFilters,
    requestFilters,
    query,
    tasks,
    refreshing,
    isInitialLoading: computed(
      () => query.isPending.value && !query.data.value,
    ),
    errorKind,
    isInitialError: computed(() => errorKind.value === 'initial'),
    isBackgroundError: computed(() => errorKind.value === 'background'),
    isNextPageError: computed(() => errorKind.value === 'next-page'),
    errorMessage,
    setStatus,
    applyFilters,
    refresh,
    loadMore,
    retryLoadMore,
  }
}
