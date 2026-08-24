import type { TaskStatusDto } from '@/entities/task'

export type TaskDatePreset =
  'today' | 'yesterday' | 'last7Days' | 'last30Days' | 'custom' | 'all'

export interface TaskFilterViewModel {
  status: TaskStatusDto | null
  deviceId: string | null
  search: string
  datePreset: TaskDatePreset
  customDateRange: [number, number] | null
}
