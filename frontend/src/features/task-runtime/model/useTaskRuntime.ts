import dayjs from 'dayjs'
import {
  computed,
  onMounted,
  onUnmounted,
  ref,
  toValue,
  type MaybeRefOrGetter,
} from 'vue'

import { useTaskEventsQuery, useTaskQuery } from '@/entities/task'

export function useTaskRuntime(taskId: MaybeRefOrGetter<string | null>) {
  const taskQuery = useTaskQuery(taskId)
  const terminal = computed(() =>
    ['success', 'failed', 'lost'].includes(taskQuery.data.value?.status ?? ''),
  )
  const eventsQuery = useTaskEventsQuery(taskId, terminal)
  const events = computed(() => eventsQuery.data.value?.items ?? [])
  const metadata = computed<Record<string, unknown>>(() =>
    events.value.reduce(
      (result, event) => ({ ...result, ...event.metadata }),
      {},
    ),
  )
  const now = ref(new Date())
  let timer: ReturnType<typeof setInterval> | null = null
  onMounted(() => {
    timer = setInterval(() => {
      now.value = new Date()
    }, 1_000)
  })
  onUnmounted(() => {
    if (timer !== null) clearInterval(timer)
  })
  const durationDisplay = computed(() => {
    const task = taskQuery.data.value
    if (!task) return '—'
    const startedAt = task.started_at ?? task.created_at
    const endedAt = task.finished_at ?? now.value
    const seconds = Math.max(0, dayjs(endedAt).diff(dayjs(startedAt), 'second'))
    const minutes = Math.floor(seconds / 60)
    const remainder = seconds % 60
    return minutes > 0 ? `${minutes} 分 ${remainder} 秒` : `${remainder} 秒`
  })

  return {
    task: taskQuery.data,
    events,
    metadata,
    terminal,
    durationDisplay,
    loading: computed(
      () => taskQuery.isPending.value || eventsQuery.isPending.value,
    ),
    error: computed(
      () => taskQuery.error.value ?? eventsQuery.error.value ?? null,
    ),
    retry: async () => {
      await Promise.all([taskQuery.refetch(), eventsQuery.refetch()])
    },
    taskId: computed(() => toValue(taskId)),
  }
}
