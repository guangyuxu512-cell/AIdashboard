import type { PageDto } from '@/shared/api'
import { apiClient } from '@/shared/api'

import type {
  TaskEventListReadDto,
  TaskEventListRequest,
  TaskListItemReadDto,
  TaskListRequest,
  TaskReadDto,
} from './contracts'

function taskPath(taskId: string, suffix = ''): string {
  return `tasks/${encodeURIComponent(taskId)}${suffix}`
}

export async function getTasks(
  params: TaskListRequest,
): Promise<PageDto<TaskListItemReadDto>> {
  const response = await apiClient.get<PageDto<TaskListItemReadDto>>('tasks', {
    params,
  })
  return response.data
}

export async function getTask(taskId: string): Promise<TaskReadDto> {
  const response = await apiClient.get<TaskReadDto>(taskPath(taskId))
  return response.data
}

export async function getTaskEvents(
  taskId: string,
  params: TaskEventListRequest = {},
): Promise<TaskEventListReadDto> {
  if (params.after_seq !== undefined && params.before_seq !== undefined) {
    throw new RangeError('after_seq 与 before_seq 不能同时传入')
  }
  if (
    params.limit !== undefined &&
    (!Number.isInteger(params.limit) || params.limit < 1 || params.limit > 200)
  ) {
    throw new RangeError('limit 必须是 1 到 200 的整数')
  }

  const response = await apiClient.get<TaskEventListReadDto>(
    taskPath(taskId, '/events'),
    { params },
  )
  return response.data
}
