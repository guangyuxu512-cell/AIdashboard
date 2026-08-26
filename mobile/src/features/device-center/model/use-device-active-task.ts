import { useQueries } from '@tanstack/vue-query'
import { computed, type MaybeRefOrGetter, toValue } from 'vue'

import {
  getActiveTaskQueryOptions,
  type ActiveTaskSummaryReadDto,
  useActiveTaskQuery,
} from '@/entities/task'

export interface DeviceActiveTaskState {
  task: ActiveTaskSummaryReadDto | null | undefined
  hasSuccessfulData: boolean
  initialLoading: boolean
  initialError: boolean
  backgroundError: boolean
  errorMessage: string
  retry: () => void
}

function activeTaskErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '当前任务加载失败'
}

export function useDeviceActiveTask(
  deviceId: MaybeRefOrGetter<string | undefined>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  const query = useActiveTaskQuery(deviceId, enabled)
  const hasSuccessfulData = computed(() => query.data.value !== undefined)
  const errorMessage = computed(() => activeTaskErrorMessage(query.error.value))

  return {
    query,
    errorMessage,
    isInitialLoading: computed(
      () => query.isPending.value && !hasSuccessfulData.value,
    ),
    isInitialError: computed(
      () => query.isError.value && !hasSuccessfulData.value,
    ),
    isBackgroundError: computed(
      () => query.isError.value && hasSuccessfulData.value,
    ),
  }
}

export function useDeviceActiveTasks(
  deviceIds: MaybeRefOrGetter<readonly string[]>,
) {
  const queries = useQueries({
    queries: () =>
      toValue(deviceIds).map((deviceId) => getActiveTaskQueryOptions(deviceId)),
  })

  const states = computed<Record<string, DeviceActiveTaskState>>(() => {
    const entries = toValue(deviceIds).map((deviceId, index) => {
      const query = queries.value[index]
      if (!query) {
        return [
          deviceId,
          {
            task: undefined,
            hasSuccessfulData: false,
            initialLoading: true,
            initialError: false,
            backgroundError: false,
            errorMessage: '当前任务加载失败',
            retry: () => undefined,
          } satisfies DeviceActiveTaskState,
        ] as const
      }

      const hasSuccessfulData = query.data !== undefined
      return [
        deviceId,
        {
          task: query.data,
          hasSuccessfulData,
          initialLoading: query.isPending && !hasSuccessfulData,
          initialError: query.isError && !hasSuccessfulData,
          backgroundError: query.isError && hasSuccessfulData,
          errorMessage: activeTaskErrorMessage(query.error),
          retry: () => {
            void query.refetch()
          },
        } satisfies DeviceActiveTaskState,
      ] as const
    })

    return Object.fromEntries(entries)
  })

  return { queries, states }
}
