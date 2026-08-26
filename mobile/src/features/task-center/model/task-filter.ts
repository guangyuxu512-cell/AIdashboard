import type { TaskListFilters, TaskStatusDto } from '@/entities/task'

export type TaskStatusFilter = 'all' | TaskStatusDto
export type TaskDatePreset =
  'today' | 'yesterday' | 'last-7-days' | 'last-30-days' | 'custom' | 'all-time'

export const TASK_DATE_PRESET_OPTIONS = [
  { text: '今天', value: 'today' },
  { text: '昨天', value: 'yesterday' },
  { text: '最近 7 天', value: 'last-7-days' },
  { text: '最近 30 天', value: 'last-30-days' },
  { text: '自定义', value: 'custom' },
  { text: '全部时间', value: 'all-time' },
] as const satisfies readonly { text: string; value: TaskDatePreset }[]

export interface TaskFilterDraft {
  search: string
  deviceId: string | undefined
  deviceName: string
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
    case 'last-30-days':
      return createTaskDateRange(shiftLocalDays(today, -29), today)
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

export function formatTaskDateFilterLabel(draft: TaskFilterDraft): string {
  if (draft.datePreset === 'custom') return formatTaskDateRange(draft.dateRange)
  return (
    TASK_DATE_PRESET_OPTIONS.find((option) => option.value === draft.datePreset)
      ?.text ?? '最近 7 天'
  )
}

export function buildTaskListFilters(
  status: TaskStatusFilter,
  draft: TaskFilterDraft,
  now = new Date(),
): TaskListFilters {
  const search = draft.search.trim()
  const range =
    draft.datePreset === 'all-time'
      ? null
      : draft.datePreset === 'custom'
        ? createTaskDateRange(draft.dateRange[0], draft.dateRange[1])
        : createTaskPresetDateRange(draft.datePreset, now)

  return {
    ...(status === 'all' ? {} : { status }),
    ...(draft.deviceId ? { deviceId: draft.deviceId } : {}),
    ...(search ? { search } : {}),
    ...(range
      ? { createdFrom: range.createdFrom, createdTo: range.createdTo }
      : {}),
  }
}

export function createDefaultTaskFilterDraft(
  now = new Date(),
): TaskFilterDraft {
  const range = createDefaultTaskDateRange(now)
  return {
    search: '',
    deviceId: undefined,
    deviceName: '',
    datePreset: 'last-7-days',
    dateRange: [range.start, range.endInclusive],
  }
}
