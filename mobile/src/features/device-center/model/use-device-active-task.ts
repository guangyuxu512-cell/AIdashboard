import { computed, type MaybeRefOrGetter } from 'vue'

import { useActiveTaskQuery } from '@/entities/task'

export function useDeviceActiveTask(
  deviceId: MaybeRefOrGetter<string | undefined>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  const query = useActiveTaskQuery(deviceId, enabled)
  const hasSuccessfulData = computed(() => query.data.value !== undefined)
  const errorMessage = computed(() => {
    const error = query.error.value
    return error instanceof Error ? error.message : '当前任务加载失败'
  })

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
