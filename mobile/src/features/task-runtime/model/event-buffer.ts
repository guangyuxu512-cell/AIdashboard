import type { TaskEventReadDto } from '@/entities/task'

export const MOBILE_TASK_EVENT_LIMIT = 500
export const MOBILE_TASK_EVENT_PAGE_SIZE = 100

export interface MergeTaskEventsResult {
  events: TaskEventReadDto[]
  dropped: number
}

export function mergeTaskEvents(
  current: readonly TaskEventReadDto[],
  incoming: readonly TaskEventReadDto[],
  limit = MOBILE_TASK_EVENT_LIMIT,
): MergeTaskEventsResult {
  const bySequence = new Map<number, TaskEventReadDto>()
  for (const event of current) bySequence.set(event.seq, event)
  for (const event of incoming) bySequence.set(event.seq, event)

  const sorted = [...bySequence.values()].sort(
    (left, right) => left.seq - right.seq,
  )
  const dropped = Math.max(0, sorted.length - limit)
  return {
    events: dropped > 0 ? sorted.slice(dropped) : sorted,
    dropped,
  }
}
