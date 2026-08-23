import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/vue-query'
import { computed, toValue, watch, type MaybeRefOrGetter } from 'vue'

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
  let nextAfterSeq = 0
  let events: TaskEventReadDto[] = []

  watch(
    () => toValue(taskId),
    (value) => {
      if (value !== currentTaskId) {
        currentTaskId = value
        nextAfterSeq = 0
        events = []
      }
    },
    { immediate: true },
  )

  return useQuery({
    queryKey: computed(() => taskQueryKeys.events(toValue(taskId))),
    queryFn: async (): Promise<TaskEventListReadDto> => {
      const id = toValue(taskId)!
      if (id !== currentTaskId) {
        currentTaskId = id
        nextAfterSeq = 0
        events = []
      }
      const page = await taskDataSource.listEvents(id, nextAfterSeq)
      events = mergeTaskEvents(events, page.items)
      nextAfterSeq = page.next_after_seq
      return { ...page, after_seq: 0, items: [...events] }
    },
    enabled: computed(() => Boolean(toValue(taskId))),
    refetchInterval: computed(() =>
      getTaskEventsRefetchInterval(toValue(terminal)),
    ),
  })
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
