import { useQuery } from '@tanstack/vue-query'
import {
  computed,
  type MaybeRefOrGetter,
  onBeforeUnmount,
  ref,
  toValue,
  watch,
} from 'vue'

import {
  getTaskEvents,
  isTerminalTaskStatus,
  type TaskEventReadDto,
  type TaskStatusDto,
} from '@/entities/task'
import { canRunBackgroundFetch } from '@/shared/utils/query-connectivity'

import {
  mergeTaskEvents,
  MOBILE_TASK_EVENT_LIMIT,
  MOBILE_TASK_EVENT_PAGE_SIZE,
} from './event-buffer'
import {
  createExclusiveDrainController,
  drainTaskEventPages,
} from './runtime-drain'

export const TASK_RUNTIME_POLL_INTERVAL_MS = 2_000

export function shouldPollTaskRuntime(
  status: TaskStatusDto | undefined,
): boolean {
  return Boolean(status && !isTerminalTaskStatus(status))
}

export function useTaskRuntime(
  taskId: MaybeRefOrGetter<string>,
  status: MaybeRefOrGetter<TaskStatusDto | undefined>,
  enabled: MaybeRefOrGetter<boolean> = true,
) {
  const events = ref<TaskEventReadDto[]>([])
  const initialized = ref(false)
  const hasMoreBefore = ref(false)
  const loadingEarlier = ref(false)
  const earlierError = ref<string | null>(null)
  const backgroundError = ref<string | null>(null)
  const reachedMemoryLimit = ref(false)
  const draining = ref(false)
  const nextAfterSequence = ref<number | null>(null)
  let disposed = false
  let generation = 0
  let pollTimer: ReturnType<typeof setInterval> | undefined

  const firstSequence = computed(() => events.value[0]?.seq ?? null)
  const lastSequence = computed(
    () => events.value[events.value.length - 1]?.seq ?? null,
  )

  function mergeRuntimeEvents(incoming: readonly TaskEventReadDto[]): void {
    const merged = mergeTaskEvents(events.value, incoming)
    events.value = merged.events
    if (merged.dropped > 0 || events.value.length >= MOBILE_TASK_EVENT_LIMIT) {
      reachedMemoryLimit.value = true
    }
  }

  async function runDrain(): Promise<void> {
    const taskIdSnapshot = toValue(taskId)
    const generationSnapshot = generation
    const startAfterSeq = nextAfterSequence.value
    if (startAfterSeq === null) return

    draining.value = true
    try {
      const result = await drainTaskEventPages({
        taskId: taskIdSnapshot,
        startAfterSeq,
        mergePage: (response) => mergeRuntimeEvents(response.items),
        isDisposed: () =>
          disposed ||
          generationSnapshot !== generation ||
          taskIdSnapshot !== toValue(taskId),
      })
      if (generationSnapshot !== generation || disposed) return
      nextAfterSequence.value = result.nextAfterSeq
      backgroundError.value = null
    } catch (error) {
      if (generationSnapshot !== generation || disposed) return
      backgroundError.value =
        error instanceof Error ? error.message : '运行日志同步失败'
    } finally {
      if (generationSnapshot === generation && !disposed) {
        draining.value = false
      }
    }
  }

  const drainController = createExclusiveDrainController(
    () =>
      !disposed &&
      toValue(enabled) &&
      initialized.value &&
      nextAfterSequence.value !== null,
    runDrain,
  )

  function requestDrain(): Promise<void> {
    return drainController.request()
  }

  function stopPolling(): void {
    if (pollTimer !== undefined) clearInterval(pollTimer)
    pollTimer = undefined
  }

  function syncPolling(
    currentStatus: TaskStatusDto | undefined,
    isEnabled: boolean,
  ): void {
    stopPolling()
    if (!isEnabled) return
    if (shouldPollTaskRuntime(currentStatus)) {
      pollTimer = setInterval(() => {
        if (!canRunBackgroundFetch()) return
        void requestDrain()
      }, TASK_RUNTIME_POLL_INTERVAL_MS)
      return
    }
    if (currentStatus && isTerminalTaskStatus(currentStatus)) {
      void requestDrain()
    }
  }

  watch(
    () => toValue(taskId),
    () => {
      generation += 1
      events.value = []
      initialized.value = false
      hasMoreBefore.value = false
      earlierError.value = null
      backgroundError.value = null
      reachedMemoryLimit.value = false
      draining.value = false
      nextAfterSequence.value = null
    },
    { flush: 'sync' },
  )

  const eventQuery = useQuery({
    queryKey: computed(() => ['tasks', 'runtime-events', toValue(taskId)]),
    enabled: computed(() => Boolean(toValue(taskId)) && toValue(enabled)),
    queryFn: () =>
      getTaskEvents(toValue(taskId), {
        limit: MOBILE_TASK_EVENT_PAGE_SIZE,
      }),
  })

  watch(
    eventQuery.data,
    (response) => {
      if (!response || disposed) return
      mergeRuntimeEvents(response.items)
      nextAfterSequence.value = response.next_after_seq
      hasMoreBefore.value = response.has_more_before
      initialized.value = true
      void requestDrain()
    },
    { immediate: true },
  )

  watch(
    [() => toValue(status), () => toValue(enabled)] as const,
    ([currentStatus, isEnabled]) => syncPolling(currentStatus, isEnabled),
    { immediate: true },
  )

  async function loadEarlier(): Promise<void> {
    const remainingCapacity = MOBILE_TASK_EVENT_LIMIT - events.value.length
    if (
      loadingEarlier.value ||
      !hasMoreBefore.value ||
      firstSequence.value === null ||
      remainingCapacity <= 0
    ) {
      if (remainingCapacity <= 0) reachedMemoryLimit.value = true
      return
    }

    const generationSnapshot = generation
    loadingEarlier.value = true
    earlierError.value = null
    try {
      const response = await getTaskEvents(toValue(taskId), {
        before_seq: firstSequence.value,
        limit: Math.min(MOBILE_TASK_EVENT_PAGE_SIZE, remainingCapacity),
      })
      if (generationSnapshot !== generation || disposed) return
      mergeRuntimeEvents(response.items)
      hasMoreBefore.value = response.has_more_before
    } catch (error) {
      if (generationSnapshot !== generation || disposed) return
      earlierError.value =
        error instanceof Error ? error.message : '更早日志加载失败'
    } finally {
      if (generationSnapshot === generation && !disposed) {
        loadingEarlier.value = false
      }
    }
  }

  onBeforeUnmount(() => {
    disposed = true
    generation += 1
    stopPolling()
  })

  return {
    events,
    initialized,
    hasMoreBefore,
    loadingEarlier,
    earlierError,
    backgroundError,
    reachedMemoryLimit,
    draining,
    firstSequence,
    lastSequence,
    nextAfterSequence,
    eventQuery,
    requestDrain,
    loadEarlier,
  }
}
