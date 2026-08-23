import { afterEach, describe, expect, it, vi } from 'vitest'

import { taskApi } from './task-api'
import {
  getTaskEventsRefetchInterval,
  loadActiveTasks,
  mergeTaskEvents,
} from './task-queries'
import type { TaskEventReadDto } from './contracts'

function event(seq: number): TaskEventReadDto {
  return {
    event_id: `event-${seq}`,
    task_id: 'task-1',
    seq,
    event_type: 'log',
    level: 'worker',
    message: `event ${seq}`,
    event_at: '2026-08-22T00:00:00Z',
    metadata: {},
    created_at: '2026-08-22T00:00:00Z',
  }
}

describe('task queries', () => {
  afterEach(() => vi.restoreAllMocks())

  it('merges incremental event pages by sequence without duplicates', () => {
    expect(
      mergeTaskEvents([event(1), event(2)], [event(2), event(3)]).map(
        (item) => item.seq,
      ),
    ).toEqual([1, 2, 3])
  })

  it('stops event polling for terminal tasks', () => {
    expect(getTaskEventsRefetchInterval(false)).toBe(1_000)
    expect(getTaskEventsRefetchInterval(true)).toBe(false)
  })

  it('degrades one failed active-task lookup without failing the device list', async () => {
    vi.spyOn(taskApi, 'getActive').mockImplementation(async (deviceId) => {
      if (deviceId === 'device-failed')
        throw new Error('auxiliary query failed')
      return null
    })

    await expect(
      loadActiveTasks(['device-ok', 'device-failed']),
    ).resolves.toEqual({ 'device-ok': null, 'device-failed': null })
  })

  it('keeps the previous active summary when a background lookup fails', async () => {
    const previous = {
      'device-failed': {
        task_id: 'task-1',
        target_device_id: 'device-failed',
        skill_id: 'yingdao.app.run',
        execution_display_name: '原子模式单店模式',
        status: 'running',
        started_at: '2026-08-23T12:00:00Z',
        created_at: '2026-08-23T12:00:00Z',
        latest_event: null,
      },
    } as const
    vi.spyOn(taskApi, 'getActive').mockRejectedValue(
      new Error('background refresh failed'),
    )

    await expect(
      loadActiveTasks(['device-failed'], previous),
    ).resolves.toEqual(previous)
  })
})
