import { describe, expect, it } from 'vitest'

import type { TaskEventReadDto } from '@/entities/task'
import {
  deriveCurrentTaskMessage,
  deriveTaskProgress,
  getRuntimeRetentionState,
  getTaskResultSummary,
  mergeTaskEvents,
  MOBILE_TASK_EVENT_LIMIT,
  shouldPollTaskRuntime,
} from '@/features/task-runtime'

function event(
  seq: number,
  eventType: TaskEventReadDto['event_type'] = 'log',
  message = `事件 ${seq}`,
  metadata: Record<string, unknown> = {},
): TaskEventReadDto {
  return {
    event_id: `event-${seq}`,
    task_id: 'task-1',
    seq,
    event_type: eventType,
    level: 'info',
    message,
    event_at: '2026-08-26T00:00:00Z',
    metadata,
    created_at: '2026-08-26T00:00:00Z',
  }
}

describe('task runtime projection and buffer', () => {
  it('deduplicates by seq, sorts ascending and retains the newest 500 events', () => {
    const current = Array.from({ length: 450 }, (_, index) => event(index + 1))
    const incoming = Array.from({ length: 100 }, (_, index) =>
      event(index + 401),
    )
    const merged = mergeTaskEvents(current, incoming)

    expect(merged.events).toHaveLength(MOBILE_TASK_EVENT_LIMIT)
    expect(merged.events[0]?.seq).toBe(1)
    expect(merged.events.at(-1)?.seq).toBe(500)
    expect(merged.dropped).toBe(0)

    const overflow = mergeTaskEvents(merged.events, [event(501), event(502)])
    expect(overflow.events[0]?.seq).toBe(3)
    expect(overflow.events.at(-1)?.seq).toBe(502)
    expect(overflow.dropped).toBe(2)
  })

  it('accepts only Backend-valid integer progress metadata', () => {
    expect(
      deriveTaskProgress([
        event(1, 'progress', '有总数', { current: 3, total: 10 }),
      ]),
    ).toEqual({ current: 3, total: 10 })
    expect(
      deriveTaskProgress([
        event(1, 'progress', '无总数', { current: 3, total: null }),
      ]),
    ).toEqual({ current: 3, total: null })
    expect(deriveTaskProgress([event(1, 'log', '完成 90/100')])).toBeNull()
  })

  it.each([
    { current: true, total: 10 },
    { current: 1.5, total: 10 },
    { current: -1, total: 10 },
    { current: 1, total: true },
    { current: 1, total: 0 },
    { current: 1, total: 1.5 },
    { current: 11, total: 10 },
    { current: 1 },
  ])('rejects invalid progress metadata %#', (metadata) => {
    expect(
      deriveTaskProgress([event(1, 'progress', '无效进度', metadata)]),
    ).toBeNull()
  })

  it('does not fall back past an invalid latest progress event', () => {
    expect(
      deriveTaskProgress([
        event(1, 'progress', '旧进度', { current: 2, total: 10 }),
        event(2, 'progress', '坏进度', { current: 12, total: 10 }),
      ]),
    ).toBeNull()
  })

  it('uses only progress, status and log priority for current information', () => {
    expect(
      deriveCurrentTaskMessage([
        event(1, 'log', '日志信息'),
        event(2, 'completed', '完成事件'),
        event(3, 'failed', '失败事件'),
      ]),
    ).toBe('日志信息')
    expect(
      deriveCurrentTaskMessage([
        event(1, 'progress', '结构化进度信息', {
          current: 1,
          total: null,
        }),
        event(2, 'status', '状态信息'),
        event(3, 'log', '较新的日志'),
      ]),
    ).toBe('结构化进度信息')
  })

  it('renders only an explicit success summary with a safe fallback', () => {
    expect(getTaskResultSummary({ summary: '共同步 8 个订单', raw: {} })).toBe(
      '共同步 8 个订单',
    )
    expect(getTaskResultSummary({ summary: ' ', secret: 'hidden' })).toBe(
      '任务已成功完成',
    )
  })

  it('distinguishes all four retention states from marker and event count', () => {
    expect(getRuntimeRetentionState(null, 0)).toBe('never-recorded')
    expect(getRuntimeRetentionState(null, 1)).toBe('complete')
    expect(getRuntimeRetentionState('2026-08-26T00:00:00Z', 0)).toBe(
      'purged-empty',
    )
    expect(getRuntimeRetentionState('2026-08-26T00:00:00Z', 1)).toBe(
      'purged-partial',
    )
  })

  it('polls only nonterminal tasks', () => {
    expect(shouldPollTaskRuntime('pending')).toBe(true)
    expect(shouldPollTaskRuntime('running')).toBe(true)
    expect(shouldPollTaskRuntime('success')).toBe(false)
    expect(shouldPollTaskRuntime('failed')).toBe(false)
    expect(shouldPollTaskRuntime('lost')).toBe(false)
  })
})
