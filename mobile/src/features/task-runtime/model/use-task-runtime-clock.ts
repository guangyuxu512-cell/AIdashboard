import { type MaybeRefOrGetter, onScopeDispose, ref, toValue, watch } from 'vue'

export const TASK_RUNTIME_CLOCK_INTERVAL_MS = 1_000

export function useTaskRuntimeClock(
  startedAt: MaybeRefOrGetter<string | null>,
  finishedAt: MaybeRefOrGetter<string | null>,
  intervalMs = TASK_RUNTIME_CLOCK_INTERVAL_MS,
) {
  const now = ref(new Date())
  let timer: ReturnType<typeof setInterval> | undefined

  function stop(): void {
    if (timer !== undefined) clearInterval(timer)
    timer = undefined
  }

  watch(
    () => [toValue(startedAt), toValue(finishedAt)] as const,
    ([start, finish]) => {
      stop()
      now.value = new Date()
      if (start && !finish) {
        timer = setInterval(() => {
          now.value = new Date()
        }, intervalMs)
      }
    },
    { immediate: true },
  )

  onScopeDispose(stop)
  return now
}
