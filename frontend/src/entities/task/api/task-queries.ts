import { useMutation, useQuery } from '@tanstack/vue-query'
import { computed, toValue, type MaybeRefOrGetter } from 'vue'

import { taskApi } from './task-api'

export const taskQueryKeys = {
  detail: (taskId: string | null) => ['tasks', 'detail', taskId] as const,
}

export function useTaskQuery(taskId: MaybeRefOrGetter<string | null>) {
  return useQuery({
    queryKey: computed(() => taskQueryKeys.detail(toValue(taskId))),
    queryFn: () => taskApi.get(toValue(taskId)!),
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
  return useMutation({ mutationFn: taskApi.create })
}
