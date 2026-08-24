import type {
  TaskEventReadDto,
  TaskReadDto,
  TaskStatusDto,
} from '@/entities/task'

export interface TaskResultSummary {
  summary: string
  fields: [string, string | number | boolean][]
}

export interface TaskFailureSummary {
  code: string | null
  message: string
}

export function getLatestProgressEvent(
  events: TaskEventReadDto[],
): TaskEventReadDto | undefined {
  return [...events]
    .reverse()
    .find((event) => event.event_type === 'progress')
}

export function getProgressDisplay(
  event: TaskEventReadDto | undefined,
): string {
  const current = event?.metadata.current
  const total = event?.metadata.total
  if (typeof current !== 'number') return '—'
  return typeof total === 'number' ? `${current} / ${total}` : String(current)
}

export function getCurrentRuntimeMessage(events: TaskEventReadDto[]): string {
  const latestFirst = [...events].reverse()
  return (
    latestFirst.find((event) => event.event_type === 'progress')?.message ??
    latestFirst.find((event) => event.event_type === 'status')?.message ??
    latestFirst.find((event) => event.event_type === 'log')?.message ??
    '—'
  )
}

export function summarizeTaskResult(
  status: TaskStatusDto,
  result: Record<string, unknown> | null,
): TaskResultSummary | null {
  if (status !== 'success' || !result) return null
  const summary =
    typeof result.summary === 'string' && result.summary.trim()
      ? result.summary
      : '任务已成功完成'
  const fields = Object.entries(result)
    .filter(
      ([key, value]) =>
        key !== 'summary' &&
        !/(token|cookie|credential|password|secret)/i.test(key) &&
        ['string', 'number', 'boolean'].includes(typeof value),
    )
    .slice(0, 6) as [string, string | number | boolean][]
  return { summary, fields }
}

export function summarizeTaskFailure(
  task: Pick<TaskReadDto, 'status' | 'error_code' | 'error_message'>,
): TaskFailureSummary | null {
  if (!['failed', 'lost'].includes(task.status)) return null
  return {
    code: task.error_code,
    message: task.error_message || '任务未能正常完成',
  }
}
