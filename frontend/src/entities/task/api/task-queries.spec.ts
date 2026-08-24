import { afterEach, describe, expect, it, vi } from 'vitest'

import { taskDataSource } from './task-data-source'
import {
  getTaskEventsRefetchInterval,
  limitTaskEvents,
  loadActiveTasks,
  mergeTaskEvents,
  taskQueryKeys,
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

  it('bounds the rendered event window while preserving newest sequence order', () => {
    const items = Array.from({ length: 1_200 }, (_, index) => event(index + 1))

    expect(limitTaskEvents(items).map((item) => item.seq)).toEqual(
      Array.from({ length: 1_000 }, (_, index) => index + 201),
    )
  })

  it('includes both created boundaries in the Task list query key', () => {
    const params = {
      page: 1,
      pageSize: 10,
      filters: {
        status: 'failed' as const,
        deviceId: 'device-1',
        search: 'fixture',
        createdFrom: '2026-08-17T00:00:00.000Z',
        createdTo: '2026-08-24T00:00:00.000Z',
      },
    }

    expect(taskQueryKeys.list(params)).toEqual(['tasks', 'list', params])
  })

  it('degrades one failed active-task lookup without failing the device list', async () => {
    vi.spyOn(taskDataSource, 'getActive').mockImplementation(
      async (deviceId) => {
        if (deviceId === 'device-failed')
          throw new Error('auxiliary query failed')
        return null
      },
    )

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
    vi.spyOn(taskDataSource, 'getActive').mockRejectedValue(
      new Error('background refresh failed'),
    )

    await expect(loadActiveTasks(['device-failed'], previous)).resolves.toEqual(
      previous,
    )
  })
})
