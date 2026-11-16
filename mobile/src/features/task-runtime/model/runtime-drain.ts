import { getTaskEvents, type TaskEventListReadDto } from '@/entities/task'

import { MOBILE_TASK_EVENT_PAGE_SIZE } from './event-buffer'

export type TaskEventDrainStopReason =
  'caught-up' | 'cursor-stalled' | 'disposed'

export interface TaskEventDrainResult {
  nextAfterSeq: number
  requestCount: number
  stopReason: TaskEventDrainStopReason
}

export interface DrainTaskEventPagesOptions {
  taskId: string
  startAfterSeq: number
  mergePage: (response: TaskEventListReadDto) => void
  isDisposed: () => boolean
  fetchPage?: typeof getTaskEvents
}

export async function drainTaskEventPages({
  taskId,
  startAfterSeq,
  mergePage,
  isDisposed,
  fetchPage = getTaskEvents,
}: DrainTaskEventPagesOptions): Promise<TaskEventDrainResult> {
  let cursor = startAfterSeq
  let requestCount = 0

  while (true) {
    if (isDisposed()) {
      return { nextAfterSeq: cursor, requestCount, stopReason: 'disposed' }
    }

    const response = await fetchPage(taskId, {
      after_seq: cursor,
      limit: MOBILE_TASK_EVENT_PAGE_SIZE,
    })
    requestCount += 1

    if (isDisposed()) {
      return { nextAfterSeq: cursor, requestCount, stopReason: 'disposed' }
    }

    mergePage(response)
    const nextCursor = response.next_after_seq
    if (response.items.length < MOBILE_TASK_EVENT_PAGE_SIZE) {
      return {
        nextAfterSeq: Math.max(cursor, nextCursor),
        requestCount,
        stopReason: 'caught-up',
      }
    }
    if (nextCursor <= cursor) {
      return {
        nextAfterSeq: cursor,
        requestCount,
        stopReason: 'cursor-stalled',
      }
    }
    cursor = nextCursor
  }
}

export interface ExclusiveDrainController {
  request: () => Promise<void>
  isActive: () => boolean
}

export function createExclusiveDrainController(
  canRun: () => boolean,
  run: () => Promise<void>,
): ExclusiveDrainController {
  let requested = false
  let activePromise: Promise<void> | null = null

  function request(): Promise<void> {
    requested = true
    if (!canRun()) return Promise.resolve()
    if (activePromise) return activePromise

    activePromise = (async () => {
      while (requested && canRun()) {
        requested = false
        await run()
      }
    })().finally(() => {
      activePromise = null
      if (requested && canRun()) void request()
    })

    return activePromise
  }

  return {
    request,
    isActive: () => activePromise !== null,
  }
}
