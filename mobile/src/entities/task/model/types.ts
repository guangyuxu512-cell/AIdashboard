import type {
  TaskProgressSummaryReadDto,
  TaskStatusDto,
} from '../api/contracts'

export interface TaskListItem {
  taskId: string
  targetDeviceId: string
  deviceDisplayName: string
  skillId: string
  executionName: string
  status: TaskStatusDto
  progress: TaskProgressSummaryReadDto | null
  currentMessage: string | null
  startedAt: string | null
  finishedAt: string | null
  createdAt: string
}

export interface TaskListFilters {
  status?: TaskStatusDto
  deviceId?: string
  search?: string
  createdFrom?: string
  createdTo?: string
}

export interface TaskListPage {
  items: TaskListItem[]
  total: number
  page: number
  pageSize: number
}
