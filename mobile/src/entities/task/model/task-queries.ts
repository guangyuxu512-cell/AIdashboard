import {
  type InfiniteData,
  useInfiniteQuery,
  useQuery,
  useQueryClient,
} from '@tanstack/vue-query'
import { computed, type MaybeRefOrGetter, nextTick, ref, toValue } from 'vue'

import {
  getOnlineRefetchInterval,
  mobileOnline,
} from '@/shared/utils/query-connectivity'

import type { TaskListRequest } from '../api/contracts'
import { getActiveTask, getTask, getTasks } from '../api/task-api'
import { isTerminalTaskStatus } from './status-meta'
import { mapTaskListPage } from './task-mapper'
import type { TaskListFilters, TaskListPage } from './types'

export const TASK_LIST_PAGE_SIZE = 20
export const TASK_LIST_REFRESH_INTERVAL_MS = 5_000
export const TASK_ACTIVE_REFRESH_INTERVAL_MS = 5_000

export const taskQueryKeys = {
  all: ['tasks'] as const,
  activeAll: () => [...taskQueryKeys.all, 'active'] as const,
  active: (deviceId: string) =>
    [...taskQueryKeys.activeAll(), deviceId] as const,
  list: (filters: TaskListFilters) =>
    [...taskQueryKeys.all, 'list', filters] as const,
  detail: (taskId: string) => [...taskQueryKeys.all, 'detail', taskId] as const,
}

export function getActiveTaskQueryOptions(
  deviceId: MaybeRefOrGetter<string | undefined>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  const refetchInterval = computed(() =>
    getOnlineRefetchInterval(TASK_ACTIVE_REFRESH_INTERVAL_MS),
  )
  return {
    queryKey: computed(() => taskQueryKeys.active(toValue(deviceId) ?? '')),
    queryFn: () => getActiveTask(toValue(deviceId) ?? ''),
    enabled: computed(() => Boolean(toValue(deviceId)) && toValue(enabled)),
    refetchInterval,
  }
}

export function useActiveTaskQuery(
  deviceId: MaybeRefOrGetter<string | undefined>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  return useQuery(getActiveTaskQueryOptions(deviceId, enabled))
}

export function getNextTaskPageParam(
  lastPage: TaskListPage,
): number | undefined {
  if (lastPage.items.length === 0) return undefined
  return lastPage.page * lastPage.pageSize < lastPage.total
    ? lastPage.page + 1
    : undefined
}

export function toTaskListRequest(
  filters: TaskListFilters,
  page: number,
): TaskListRequest {
  return {
    page,
    page_size: TASK_LIST_PAGE_SIZE,
    ...(filters.status ? { status: filters.status } : {}),
    ...(filters.deviceId ? { device_id: filters.deviceId } : {}),
    ...(filters.search ? { search: filters.search } : {}),
    ...(filters.createdFrom ? { created_from: filters.createdFrom } : {}),
    ...(filters.createdTo ? { created_to: filters.createdTo } : {}),
  }
}

export function getTaskListRefetchInterval(
  data: InfiniteData<TaskListPage, number> | undefined,
): number | false {
  return data && data.pages.length > 1 ? false : TASK_LIST_REFRESH_INTERVAL_MS
}

interface QueryStateWithData<TData> {
  state: { data: TData | undefined }
}

function resolveTaskListRefetchInterval(
  query: QueryStateWithData<InfiniteData<TaskListPage, number>>,
): number | false {
  return getTaskListRefetchInterval(query.state.data)
}

function resolveTaskDetailRefetchInterval(
  query: QueryStateWithData<Awaited<ReturnType<typeof getTask>>>,
): number | false {
  const task = query.state.data
  return task && !isTerminalTaskStatus(task.status) ? 2_000 : false
}

export function useTaskListQuery(filters: MaybeRefOrGetter<TaskListFilters>) {
  const queryClient = useQueryClient()
  const queryKey = computed(() => taskQueryKeys.list(toValue(filters)))
  const manualRefreshing = ref(false)
  const effectiveRefetchInterval = computed(() =>
    manualRefreshing.value || !mobileOnline.value
      ? false
      : resolveTaskListRefetchInterval,
  )
  const query = useInfiniteQuery({
    queryKey,
    initialPageParam: 1,
    queryFn: async ({ pageParam }) =>
      mapTaskListPage(
        await getTasks(toTaskListRequest(toValue(filters), pageParam)),
      ),
    getNextPageParam: getNextTaskPageParam,
    refetchInterval: effectiveRefetchInterval,
  })

  async function refreshFromStart(): Promise<void> {
    const filtersSnapshot = { ...toValue(filters) }
    const queryKeySnapshot = taskQueryKeys.list(filtersSnapshot)
    manualRefreshing.value = true
    await nextTick()
    try {
      await queryClient.cancelQueries({
        queryKey: queryKeySnapshot,
        exact: true,
      })
      const firstPage = mapTaskListPage(
        await getTasks(toTaskListRequest(filtersSnapshot, 1)),
      )
      await queryClient.cancelQueries({
        queryKey: queryKeySnapshot,
        exact: true,
      })
      queryClient.setQueryData<InfiniteData<TaskListPage, number>>(
        queryKeySnapshot,
        { pages: [firstPage], pageParams: [1] },
      )
    } finally {
      manualRefreshing.value = false
    }
  }

  return { ...query, refreshFromStart }
}

export function useTaskDetailQuery(taskId: MaybeRefOrGetter<string>) {
  const refetchInterval = computed(() =>
    mobileOnline.value ? resolveTaskDetailRefetchInterval : false,
  )
  return useQuery({
    queryKey: computed(() => taskQueryKeys.detail(toValue(taskId))),
    queryFn: () => getTask(toValue(taskId)),
    enabled: computed(() => Boolean(toValue(taskId))),
    refetchInterval,
  })
}
