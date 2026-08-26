import type {
  TaskEventReadDto,
  TaskProgressSummaryReadDto,
} from '@/entities/task'

export type RuntimeRetentionState =
  'never-recorded' | 'complete' | 'purged-empty' | 'purged-partial'

export const RUNTIME_RETENTION_TEXT: Record<RuntimeRetentionState, string> = {
  'never-recorded': '暂无运行日志',
  complete: '',
  'purged-empty': '运行日志已清理',
  'purged-partial': '较早日志已清理',
}

export function getRuntimeRetentionState(
  purgedAt: string | null,
  eventCount: number,
): RuntimeRetentionState {
  if (purgedAt) return eventCount > 0 ? 'purged-partial' : 'purged-empty'
  return eventCount > 0 ? 'complete' : 'never-recorded'
}

function readInteger(
  metadata: Record<string, unknown>,
  key: string,
): number | null {
  const value = metadata[key]
  return typeof value === 'number' && Number.isInteger(value) ? value : null
}

export function deriveTaskProgress(
  events: readonly TaskEventReadDto[],
): TaskProgressSummaryReadDto | null {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index]
    if (event.event_type !== 'progress') continue
    const current = readInteger(event.metadata, 'current')
    if (current === null || current < 0) return null

    if (event.metadata.total === null) return { current, total: null }
    const total = readInteger(event.metadata, 'total')
    if (total === null || total <= 0 || current > total) return null
    return { current, total }
  }
  return null
}

const CURRENT_MESSAGE_TYPE_PRIORITY = [
  ['progress'],
  ['status'],
  ['log'],
] as const

export function deriveCurrentTaskMessage(
  events: readonly TaskEventReadDto[],
): string | null {
  for (const eventTypes of CURRENT_MESSAGE_TYPE_PRIORITY) {
    for (let index = events.length - 1; index >= 0; index -= 1) {
      const event = events[index]
      if (!eventTypes.includes(event.event_type as never)) continue
      const message = event.message.trim()
      if (message) return message
    }
  }
  return null
}

export function getTaskResultSummary(
  result: Record<string, unknown> | null,
): string {
  const summary = result?.summary
  return typeof summary === 'string' && summary.trim()
    ? summary.trim()
    : '任务已成功完成'
}

export function formatTaskDuration(
  startedAt: string | null,
  finishedAt: string | null,
  now = new Date(),
): string {
  if (!startedAt) return '—'
  const start = new Date(startedAt).getTime()
  const end = finishedAt ? new Date(finishedAt).getTime() : now.getTime()
  if (!Number.isFinite(start) || !Number.isFinite(end) || end < start)
    return '—'

  const seconds = Math.floor((end - start) / 1_000)
  const hours = Math.floor(seconds / 3_600)
  const minutes = Math.floor((seconds % 3_600) / 60)
  const remainingSeconds = seconds % 60
  if (hours > 0) return `${hours}小时${minutes}分${remainingSeconds}秒`
  if (minutes > 0) return `${minutes}分${remainingSeconds}秒`
  return `${remainingSeconds}秒`
}

export function formatTaskDateTime(value: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date)
}
