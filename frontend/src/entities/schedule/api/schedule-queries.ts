import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/vue-query'
import { computed, toValue, type MaybeRefOrGetter } from 'vue'

import type { ScheduleSaveInput } from '../model/types'
import {
  scheduleDataSource,
  type ScheduleListParams,
} from './schedule-data-source'

export const scheduleQueryKeys = {
  all: ['schedules'] as const,
  list: (params: ScheduleListParams) => ['schedules', 'list', params] as const,
  detail: (scheduleId: string | null) =>
    ['schedules', 'detail', scheduleId] as const,
  runs: (scheduleId: string | null, timezone?: string) =>
    ['schedules', 'runs', scheduleId, timezone] as const,
}

export const SCHEDULE_LIST_REFETCH_INTERVAL_MS = 15_000

export function useScheduleListQuery(
  params: MaybeRefOrGetter<ScheduleListParams>,
) {
  return useQuery({
    queryKey: computed(() => scheduleQueryKeys.list(toValue(params))),
    queryFn: () => scheduleDataSource.list(toValue(params)),
    placeholderData: keepPreviousData,
    refetchInterval:
      scheduleDataSource.mode === 'real'
        ? SCHEDULE_LIST_REFETCH_INTERVAL_MS
        : false,
  })
}

export function useScheduleDetailQuery(
  scheduleId: MaybeRefOrGetter<string | null>,
) {
  return useQuery({
    queryKey: computed(() => scheduleQueryKeys.detail(toValue(scheduleId))),
    queryFn: () => scheduleDataSource.get(toValue(scheduleId)!),
    enabled: computed(() => Boolean(toValue(scheduleId))),
  })
}

export function useScheduleRunsQuery(
  scheduleId: MaybeRefOrGetter<string | null>,
  timezone: MaybeRefOrGetter<string>,
) {
  return useQuery({
    queryKey: computed(() =>
      scheduleQueryKeys.runs(toValue(scheduleId), toValue(timezone)),
    ),
    queryFn: () =>
      scheduleDataSource.listRuns(
        toValue(scheduleId)!,
        1,
        20,
        toValue(timezone),
      ),
    enabled: computed(() => Boolean(toValue(scheduleId))),
    placeholderData: keepPreviousData,
  })
}

export function useCreateScheduleMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: ScheduleSaveInput) => scheduleDataSource.create(input),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: scheduleQueryKeys.all }),
  })
}

export function useUpdateScheduleMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      scheduleId,
      input,
    }: {
      scheduleId: string
      input: Partial<ScheduleSaveInput>
    }) => scheduleDataSource.update(scheduleId, input),
    onSuccess: (_, variables) =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: scheduleQueryKeys.all }),
        queryClient.invalidateQueries({
          queryKey: scheduleQueryKeys.detail(variables.scheduleId),
        }),
      ]),
  })
}

export function useRemoveScheduleMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: scheduleDataSource.remove,
    onSuccess: (_, scheduleId) => {
      queryClient.removeQueries({
        queryKey: scheduleQueryKeys.detail(scheduleId),
      })
      return queryClient.invalidateQueries({ queryKey: scheduleQueryKeys.all })
    },
  })
}
