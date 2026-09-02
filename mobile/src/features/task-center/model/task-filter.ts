import type { TaskListFilters, TaskStatusDto } from '@/entities/task'

export type TaskStatusFilter =
  'all' | 'running' | 'pending' | 'exception' | 'completed'

export type TaskDatePreset =
  'today' | 'yesterday' | 'last-7-days' | 'custom' | 'all-time'

export const TASK_DATE_PRESET_OPTIONS = [
  { text: '今天', value: 'today' },
  { text: '昨天', value: 'yesterday' },
  { text: '近7天', value: 'last-7-days' },
  { text: '全部', value: 'all-time' },
] as const satisfies readonly {
  text: string
  value: Exclude<TaskDatePreset, 'custom'>
}[]

export const TASK_STATUS_FILTER_OPTIONS = [
  { label: '任务', value: 'all', statuses: [] },
  { label: '运行中', value: 'running', statuses: ['running'] },
  { label: '待运行', value: 'pending', statuses: ['pending'] },
  { label: '异常任务', value: 'exception', statuses: ['failed', 'lost'] },
  { label: '已完成', value: 'completed', statuses: ['success'] },
] as const satisfies readonly {
  label: string
  value: TaskStatusFilter
  statuses: readonly TaskStatusDto[]
}[]

export interface TaskFilterDraft {
  search: string
  datePreset: TaskDatePreset
  dateRange: readonly [Date, Date]
}

export interface TaskDateRange {
  start: Date
  endInclusive: Date
  createdFrom: string
  createdTo: string
}

function startOfLocalDay(value: Date): Date {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate())
}

function shiftLocalDays(value: Date, offset: number): Date {
  return new Date(
    value.getFullYear(),
    value.getMonth(),
    value.getDate() + offset,
  )
}

function nextLocalDay(value: Date): Date {
  return shiftLocalDays(value, 1)
}

export function createTaskDateRange(
  start: Date,
  endInclusive: Date,
): TaskDateRange {
  const normalizedStart = startOfLocalDay(start)
  const normalizedEnd = startOfLocalDay(endInclusive)
  return {
    start: normalizedStart,
    endInclusive: normalizedEnd,
    createdFrom: normalizedStart.toISOString(),
    createdTo: nextLocalDay(normalizedEnd).toISOString(),
  }
}

export function createTaskPresetDateRange(
  preset: Exclude<TaskDatePreset, 'custom' | 'all-time'>,
  now = new Date(),
): TaskDateRange {
  const today = startOfLocalDay(now)
  switch (preset) {
    case 'today':
      return createTaskDateRange(today, today)
    case 'yesterday': {
      const yesterday = shiftLocalDays(today, -1)
      return createTaskDateRange(yesterday, yesterday)
    }
    case 'last-7-days':
      return createTaskDateRange(shiftLocalDays(today, -6), today)
  }
}

export function createDefaultTaskDateRange(now = new Date()): TaskDateRange {
  return createTaskPresetDateRange('last-7-days', now)
}

export function formatTaskDateRange(range: readonly [Date, Date]): string {
  const formatter = new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
  })
  return `${formatter.format(range[0])} - ${formatter.format(range[1])}`
}

export function formatTaskDateInput(value: Date): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function parseTaskDateInput(value: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!match) return null
  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])
  const date = new Date(year, month - 1, day)
  return date.getFullYear() === year &&
    date.getMonth() === month - 1 &&
    date.getDate() === day
    ? date
    : null
}

export function formatTaskDateFilterLabel(draft: TaskFilterDraft): string {
  if (draft.datePreset === 'custom') {
    const date = draft.dateRange[0]
    return `${date.getMonth() + 1}月${date.getDate()}日`
  }
  return (
    TASK_DATE_PRESET_OPTIONS.find((option) => option.value === draft.datePreset)
      ?.text ?? '近7天'
  )
}

export function getTaskStatusFilterOption(status: TaskStatusFilter) {
  return (
    TASK_STATUS_FILTER_OPTIONS.find((option) => option.value === status) ??
    TASK_STATUS_FILTER_OPTIONS[0]
  )
}

export function buildTaskBaseFilters(
  draft: TaskFilterDraft,
  now = new Date(),
): TaskListFilters {
  const search = draft.search.trim()
  const range =
    draft.datePreset === 'all-time'
      ? null
      : draft.datePreset === 'custom'
        ? createTaskDateRange(draft.dateRange[0], draft.dateRange[0])
        : createTaskPresetDateRange(draft.datePreset, now)

  return {
    ...(search ? { search } : {}),
    ...(range
      ? { createdFrom: range.createdFrom, createdTo: range.createdTo }
      : {}),
  }
}

export function buildTaskListFilters(
  status: TaskStatusDto | 'all',
  draft: TaskFilterDraft,
  now = new Date(),
): TaskListFilters {
  return {
    ...buildTaskBaseFilters(draft, now),
    ...(status === 'all' ? {} : { status }),
  }
}

export function createDefaultTaskFilterDraft(
  now = new Date(),
): TaskFilterDraft {
  const range = createDefaultTaskDateRange(now)
  return {
    search: '',
    datePreset: 'last-7-days',
    dateRange: [range.start, range.endInclusive],
  }
}
