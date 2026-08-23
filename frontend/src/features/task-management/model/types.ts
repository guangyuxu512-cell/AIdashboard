import type { TaskStatusDto } from '@/entities/task'

export interface TaskFilterViewModel {
  status: TaskStatusDto | null
  deviceId: string | null
  search: string
}
