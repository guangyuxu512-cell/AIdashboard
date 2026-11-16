import type { TaskStatusDto } from '../api/contracts'

export const TASK_STATUSES = [
  'pending',
  'running',
  'success',
  'failed',
  'lost',
] as const satisfies readonly TaskStatusDto[]

export const TASK_STATUS_META = {
  pending: { label: '待执行', tagType: 'warning' },
  running: { label: '执行中', tagType: 'primary' },
  success: { label: '成功', tagType: 'success' },
  failed: { label: '失败', tagType: 'danger' },
  lost: { label: '已丢失', tagType: 'danger' },
} as const satisfies Record<
  TaskStatusDto,
  { label: string; tagType: 'primary' | 'success' | 'danger' | 'warning' }
>

export const TERMINAL_TASK_STATUSES: ReadonlySet<TaskStatusDto> = new Set([
  'success',
  'failed',
  'lost',
] satisfies readonly TaskStatusDto[])

export function isTerminalTaskStatus(status: TaskStatusDto): boolean {
  return TERMINAL_TASK_STATUSES.has(status)
}
