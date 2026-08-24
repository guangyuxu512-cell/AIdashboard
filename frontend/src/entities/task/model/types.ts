import type { TaskStatusDto } from '../api/contracts'

export interface TaskListFilters {
  status: TaskStatusDto | null
  deviceId: string | null
  search: string
  createdFrom: string | null
  createdTo: string | null
}

export interface TaskListItemViewModel {
  taskId: string
  deviceId: string
  deviceName: string
  skillId: string
  executionName: string
  status: TaskStatusDto
  progressDisplay: string
  currentMessage: string
  startedAtDisplay: string
  createdAt: string
}
