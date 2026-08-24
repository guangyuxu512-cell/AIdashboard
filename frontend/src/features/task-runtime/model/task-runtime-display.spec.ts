import { describe, expect, it } from 'vitest'

import type { TaskEventReadDto, TaskReadDto } from '@/entities/task'

import {
  getCurrentRuntimeMessage,
  getLatestProgressEvent,
  getProgressDisplay,
  summarizeTaskFailure,
  summarizeTaskResult,
} from './task-runtime-display'

function event(
  seq: number,
  eventType: TaskEventReadDto['event_type'],
  message: string,
  metadata: Record<string, unknown> = {},
): TaskEventReadDto {
  return {
    event_id: `event-${seq}`,
    task_id: 'task-1',
    seq,
    event_type: eventType,
    level: 'info',
    message,
    event_at: '2026-08-25T00:00:00Z',
    metadata,
    created_at: '2026-08-25T00:00:00Z',
  }
}

function failureTask(
  status: 'pending' | 'running' | 'failed' | 'lost',
): Pick<TaskReadDto, 'status' | 'error_code' | 'error_message'> {
  return {
    status,
    error_code: status === 'lost' ? 'WORKER_LEASE_EXPIRED' : 'RUNTIME_FAILED',
    error_message: status === 'lost' ? 'Worker 已失联' : '安全失败摘要',
  }
}

describe('task runtime business presentation', () => {
  it('keeps PENDING without invented progress or current information', () => {
    expect(getProgressDisplay(undefined)).toBe('—')
    expect(getCurrentRuntimeMessage([])).toBe('—')
    expect(summarizeTaskFailure(failureTask('pending'))).toBeNull()
  })

  it('uses structured RUNNING progress and its message', () => {
    const events = [
      event(1, 'status', '开始执行'),
      event(2, 'progress', '正在处理第 3 项', { current: 3, total: 10 }),
    ]
    const progress = getLatestProgressEvent(events)
    expect(getProgressDisplay(progress)).toBe('3 / 10')
    expect(getCurrentRuntimeMessage(events)).toBe('正在处理第 3 项')
  })

  it('summarizes SUCCESS without dumping nested or sensitive result data', () => {
    expect(
      summarizeTaskResult('success', {
        summary: '同步完成',
        created: 8,
        dry_run: true,
        token: 'must-not-render',
        nested: { raw: 'payload' },
      }),
    ).toEqual({
      summary: '同步完成',
      fields: [
        ['created', 8],
        ['dry_run', true],
      ],
    })
  })

  it.each([
    ['failed', 'RUNTIME_FAILED', '安全失败摘要'],
    ['lost', 'WORKER_LEASE_EXPIRED', 'Worker 已失联'],
  ] as const)('shows the safe %s error summary', (status, code, message) => {
    expect(summarizeTaskFailure(failureTask(status))).toEqual({ code, message })
  })
})
