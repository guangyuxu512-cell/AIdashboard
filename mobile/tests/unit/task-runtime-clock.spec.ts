import { effectScope, nextTick, ref } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  formatTaskDuration,
  useTaskRuntimeClock,
} from '@/features/task-runtime'

describe('running task clock', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('ticks while running and cleans up when finished or disposed', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-08-26T00:00:10Z'))
    const startedAt = ref<string | null>('2026-08-26T00:00:00Z')
    const finishedAt = ref<string | null>(null)
    const scope = effectScope()
    const now = scope.run(() =>
      useTaskRuntimeClock(startedAt, finishedAt, 1_000),
    )
    if (!now) throw new Error('clock scope failed')

    expect(formatTaskDuration(startedAt.value, null, now.value)).toBe('10秒')
    await vi.advanceTimersByTimeAsync(2_000)
    expect(formatTaskDuration(startedAt.value, null, now.value)).toBe('12秒')

    finishedAt.value = '2026-08-26T00:00:11Z'
    await nextTick()
    expect(vi.getTimerCount()).toBe(0)
    expect(
      formatTaskDuration(startedAt.value, finishedAt.value, now.value),
    ).toBe('11秒')

    finishedAt.value = null
    await nextTick()
    expect(vi.getTimerCount()).toBe(1)
    scope.stop()
    expect(vi.getTimerCount()).toBe(0)
  })
})
