import { describe, expect, it, vi } from 'vitest'

import type {
  TaskEventListReadDto,
  TaskEventListRequest,
  TaskEventReadDto,
} from '@/entities/task'
import {
  createExclusiveDrainController,
  drainTaskEventPages,
  mergeTaskEvents,
} from '@/features/task-runtime'

function event(seq: number): TaskEventReadDto {
  return {
    event_id: `event-${seq}`,
    task_id: 'task-1',
    seq,
    event_type: 'log',
    level: 'info',
    message: `事件 ${seq}`,
    event_at: '2026-08-26T00:00:00Z',
    metadata: {},
    created_at: '2026-08-26T00:00:00Z',
  }
}

function response(
  afterSeq: number,
  nextAfterSeq: number,
  items: TaskEventReadDto[],
): TaskEventListReadDto {
  return {
    task_id: 'task-1',
    after_seq: afterSeq,
    before_seq: null,
    next_after_seq: nextAfterSeq,
    next_before_seq: null,
    has_more_before: false,
    items,
  }
}

describe('task event after-seq drain', () => {
  it('uses next_after_seq and drains more than 100 events across batches', async () => {
    const requests: TaskEventListRequest[] = []
    const fetchPage = vi.fn(
      async (_taskId: string, request: TaskEventListRequest = {}) => {
        requests.push(request)
        if (requests.length === 1) {
          return response(
            100,
            200,
            Array.from({ length: 100 }, (_, index) => event(index + 101)),
          )
        }
        return response(
          200,
          250,
          Array.from({ length: 50 }, (_, index) => event(index + 201)),
        )
      },
    )

    const result = await drainTaskEventPages({
      taskId: 'task-1',
      startAfterSeq: 100,
      mergePage: () => undefined,
      isDisposed: () => false,
      fetchPage,
    })

    expect(requests).toEqual([
      { after_seq: 100, limit: 100 },
      { after_seq: 200, limit: 100 },
    ])
    expect(result).toEqual({
      nextAfterSeq: 250,
      requestCount: 2,
      stopReason: 'caught-up',
    })
  })

  it('stops without looping when the server cursor does not advance', async () => {
    const fetchPage = vi.fn(
      async (_taskId: string, request: TaskEventListRequest = {}) =>
        response(
          Number(request.after_seq),
          Number(request.after_seq),
          Array.from({ length: 100 }, (_, index) => event(index + 1)),
        ),
    )

    const result = await drainTaskEventPages({
      taskId: 'task-1',
      startAfterSeq: 50,
      mergePage: () => undefined,
      isDisposed: () => false,
      fetchPage,
    })

    expect(fetchPage).toHaveBeenCalledOnce()
    expect(result.stopReason).toBe('cursor-stalled')
    expect(result.nextAfterSeq).toBe(50)
  })

  it('still advances from a full 500-event buffer and evicts the oldest events', async () => {
    let buffered = Array.from({ length: 500 }, (_, index) => event(index + 1))
    const fetchPage = vi.fn(
      async (_taskId: string, request: TaskEventListRequest = {}) => {
        expect(request).toEqual({ after_seq: 500, limit: 100 })
        return response(
          Number(request.after_seq),
          550,
          Array.from({ length: 50 }, (_, index) => event(index + 501)),
        )
      },
    )

    const result = await drainTaskEventPages({
      taskId: 'task-1',
      startAfterSeq: 500,
      mergePage: (page) => {
        buffered = mergeTaskEvents(buffered, page.items).events
      },
      isDisposed: () => false,
      fetchPage,
    })

    expect(fetchPage).toHaveBeenCalledOnce()
    expect(result).toEqual({
      nextAfterSeq: 550,
      requestCount: 1,
      stopReason: 'caught-up',
    })
    expect(buffered).toHaveLength(500)
    expect(buffered[0]?.seq).toBe(51)
    expect(buffered.at(-1)?.seq).toBe(550)
  })

  it('drains multiple full pages and retains only the newest 500 events', async () => {
    let buffered = Array.from({ length: 450 }, (_, index) => event(index + 1))
    const fetchPage = vi.fn(
      async (_taskId: string, request: TaskEventListRequest = {}) => {
        const afterSequence = Number(request.after_seq)
        if (afterSequence < 650) {
          return response(
            afterSequence,
            afterSequence + 100,
            Array.from({ length: 100 }, (_, index) =>
              event(afterSequence + index + 1),
            ),
          )
        }
        return response(
          afterSequence,
          675,
          Array.from({ length: 25 }, (_, index) => event(651 + index)),
        )
      },
    )

    const result = await drainTaskEventPages({
      taskId: 'task-1',
      startAfterSeq: 450,
      mergePage: (page) => {
        buffered = mergeTaskEvents(buffered, page.items).events
      },
      isDisposed: () => false,
      fetchPage,
    })

    expect(fetchPage).toHaveBeenCalledTimes(3)
    expect(result).toEqual({
      nextAfterSeq: 675,
      requestCount: 3,
      stopReason: 'caught-up',
    })
    expect(buffered).toHaveLength(500)
    expect(buffered[0]?.seq).toBe(176)
    expect(buffered.at(-1)?.seq).toBe(675)
  })

  it('allows an explicit retry after a drain request fails midway', async () => {
    let cursor = 100
    let buffered = Array.from({ length: 100 }, (_, index) => event(index + 1))
    let hasFailed = false
    const fetchPage = vi.fn(
      async (_taskId: string, request: TaskEventListRequest = {}) => {
        const afterSequence = Number(request.after_seq)
        if (afterSequence === 100) {
          return response(
            100,
            200,
            Array.from({ length: 100 }, (_, index) => event(index + 101)),
          )
        }
        if (!hasFailed) {
          hasFailed = true
          throw new Error('增量同步失败')
        }
        return response(
          afterSequence,
          210,
          Array.from({ length: 10 }, (_, index) => event(index + 201)),
        )
      },
    )
    const run = async () => {
      const result = await drainTaskEventPages({
        taskId: 'task-1',
        startAfterSeq: cursor,
        mergePage: (page) => {
          buffered = mergeTaskEvents(buffered, page.items).events
        },
        isDisposed: () => false,
        fetchPage,
      })
      cursor = result.nextAfterSeq
    }
    const controller = createExclusiveDrainController(() => true, run)

    await expect(controller.request()).rejects.toThrow('增量同步失败')
    expect(controller.isActive()).toBe(false)
    await expect(controller.request()).resolves.toBeUndefined()

    expect(fetchPage).toHaveBeenCalledTimes(4)
    expect(cursor).toBe(210)
    expect(buffered).toHaveLength(210)
    expect(buffered.at(-1)?.seq).toBe(210)
    expect(controller.isActive()).toBe(false)
  })

  it('coalesces status-first and initial-event-first race signals exclusively', async () => {
    let initialized = false
    let activeRuns = 0
    let maximumConcurrency = 0
    const releases: Array<() => void> = []
    const run = vi.fn(async () => {
      activeRuns += 1
      maximumConcurrency = Math.max(maximumConcurrency, activeRuns)
      await new Promise<void>((resolve) => releases.push(resolve))
      activeRuns -= 1
    })
    const controller = createExclusiveDrainController(() => initialized, run)

    await controller.request()
    expect(run).not.toHaveBeenCalled()

    initialized = true
    const initialEventsSignal = controller.request()
    await vi.waitFor(() => expect(run).toHaveBeenCalledTimes(1))
    const terminalStatusSignal = controller.request()
    releases.shift()?.()
    await vi.waitFor(() => expect(run).toHaveBeenCalledTimes(2))
    releases.shift()?.()
    await Promise.all([initialEventsSignal, terminalStatusSignal])

    expect(maximumConcurrency).toBe(1)
    expect(controller.isActive()).toBe(false)
  })
})
