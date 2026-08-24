import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/vue-query'
import { computed, ref, toValue, watch, type MaybeRefOrGetter } from 'vue'

import { taskDataSource, type TaskListParams } from './task-data-source'
import type {
  ActiveTaskSummaryReadDto,
  TaskEventListReadDto,
  TaskEventReadDto,
} from './contracts'

export const taskQueryKeys = {
  all: ['tasks'] as const,
  list: (params: TaskListParams) => ['tasks', 'list', params] as const,
  detail: (taskId: string | null) => ['tasks', 'detail', taskId] as const,
  events: (taskId: string | null) => ['tasks', 'events', taskId] as const,
  activeByDevices: (deviceIds: string[]) =>
    ['tasks', 'active-by-devices', ...deviceIds] as const,
}

export const TASK_LIST_REFETCH_INTERVAL_MS = 5_000
export const TASK_EVENT_PAGE_LIMIT = 100
export const TASK_EVENT_RENDER_LIMIT = 1_000

export function useTaskListQuery(params: MaybeRefOrGetter<TaskListParams>) {
  return useQuery({
    queryKey: computed(() => taskQueryKeys.list(toValue(params))),
    queryFn: () => taskDataSource.list(toValue(params)),
    refetchInterval:
      taskDataSource.mode === 'real' ? TASK_LIST_REFETCH_INTERVAL_MS : false,
    placeholderData: keepPreviousData,
  })
}

export function mergeTaskEvents(
  existing: TaskEventReadDto[],
  page: TaskEventReadDto[],
): TaskEventReadDto[] {
  const bySequence = new Map(
    existing.map((event) => [event.seq, event] as const),
  )
  for (const event of page) bySequence.set(event.seq, event)
  return [...bySequence.values()].sort((left, right) => left.seq - right.seq)
}

export function limitTaskEvents(
  items: TaskEventReadDto[],
  limit = TASK_EVENT_RENDER_LIMIT,
): TaskEventReadDto[] {
  return items.length > limit ? items.slice(-limit) : items
}

export function getTaskEventsRefetchInterval(
  terminal: boolean,
): number | false {
  return terminal ? false : 1_000
}

export function useTaskEventsQuery(
  taskId: MaybeRefOrGetter<string | null>,
  terminal: MaybeRefOrGetter<boolean>,
) {
  let currentTaskId: string | null = null
  let initialized = false
  let nextAfterSeq = 0
  const events = ref<TaskEventReadDto[]>([])
  const hasEarlier = ref(false)
  const loadingEarlier = ref(false)
  const historyError = ref<unknown>(null)

  watch(
    () => toValue(taskId),
    (value) => {
      if (value !== currentTaskId) {
        currentTaskId = value
        initialized = false
        nextAfterSeq = 0
        events.value = []
        hasEarlier.value = false
        historyError.value = null
      }
    },
    { immediate: true },
  )

  const query = useQuery({
    queryKey: computed(() => taskQueryKeys.events(toValue(taskId))),
    queryFn: async (): Promise<TaskEventListReadDto> => {
      const id = toValue(taskId)!
      if (id !== currentTaskId) {
        currentTaskId = id
        initialized = false
        nextAfterSeq = 0
        events.value = []
        hasEarlier.value = false
      }
      if (!initialized) {
        const page = await taskDataSource.listEvents(id, {
          limit: TASK_EVENT_PAGE_LIMIT,
        })
        events.value = page.items
        nextAfterSeq = page.next_after_seq
        hasEarlier.value = page.has_more_before
        initialized = true
        return { ...page, items: [...events.value] }
      }
      const page = await taskDataSource.listEvents(id, {
        afterSeq: nextAfterSeq,
        limit: TASK_EVENT_PAGE_LIMIT,
      })
      const merged = mergeTaskEvents(events.value, page.items)
      if (merged.length > TASK_EVENT_RENDER_LIMIT) {
        events.value = limitTaskEvents(merged)
        hasEarlier.value = true
      } else {
        events.value = merged
      }
      nextAfterSeq = Math.max(nextAfterSeq, page.next_after_seq)
      return { ...page, after_seq: 0, items: [...events.value] }
    },
    enabled: computed(() => Boolean(toValue(taskId))),
    refetchInterval: computed(() =>
      getTaskEventsRefetchInterval(toValue(terminal)),
    ),
  })

  async function loadEarlier(): Promise<void> {
    const id = toValue(taskId)
    const oldestSeq = events.value[0]?.seq
    const capacity = TASK_EVENT_RENDER_LIMIT - events.value.length
    if (
      !id ||
      oldestSeq === undefined ||
      !hasEarlier.value ||
      loadingEarlier.value ||
      capacity <= 0
    ) {
      return
    }
    loadingEarlier.value = true
    historyError.value = null
    try {
      const page = await taskDataSource.listEvents(id, {
        beforeSeq: oldestSeq,
        limit: Math.min(TASK_EVENT_PAGE_LIMIT, capacity),
      })
      events.value = mergeTaskEvents(page.items, events.value)
      hasEarlier.value = page.has_more_before
    } catch (error) {
      historyError.value = error
    } finally {
      loadingEarlier.value = false
    }
  }

  return {
    query,
    events: computed(() => events.value),
    hasEarlier: computed(() => hasEarlier.value),
    loadingEarlier: computed(() => loadingEarlier.value),
    historyError: computed(() => historyError.value),
    historyLimitReached: computed(
      () => hasEarlier.value && events.value.length >= TASK_EVENT_RENDER_LIMIT,
    ),
    loadEarlier,
  }
}

export async function loadActiveTasks(
  deviceIds: string[],
  previous: Record<string, ActiveTaskSummaryReadDto | null> = {},
): Promise<Record<string, ActiveTaskSummaryReadDto | null>> {
  const results = await Promise.allSettled(
    deviceIds.map((deviceId) => taskDataSource.getActive(deviceId)),
  )
  return Object.fromEntries(
    deviceIds.map((deviceId, index) => [
      deviceId,
      results[index]?.status === 'fulfilled'
        ? results[index].value
        : (previous[deviceId] ?? null),
    ]),
  )
}

export function useActiveTasksQuery(
  deviceIds: MaybeRefOrGetter<string[]>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  const queryClient = useQueryClient()
  return useQuery({
    queryKey: computed(() => taskQueryKeys.activeByDevices(toValue(deviceIds))),
    queryFn: () => {
      const ids = toValue(deviceIds)
      return loadActiveTasks(
        ids,
        queryClient.getQueryData(taskQueryKeys.activeByDevices(ids)),
      )
    },
    enabled: computed(() => toValue(enabled) && toValue(deviceIds).length > 0),
    refetchInterval: computed(() => (toValue(enabled) ? 1_000 : false)),
    placeholderData: keepPreviousData,
  })
}

export function useTaskQuery(taskId: MaybeRefOrGetter<string | null>) {
  return useQuery({
    queryKey: computed(() => taskQueryKeys.detail(toValue(taskId))),
    queryFn: () => taskDataSource.get(toValue(taskId)!),
    enabled: computed(() => Boolean(toValue(taskId))),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'success' || status === 'failed' || status === 'lost'
        ? false
        : 1_000
    },
  })
}

export function useCreateTaskMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: taskDataSource.create,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: taskQueryKeys.all }),
  })
}
