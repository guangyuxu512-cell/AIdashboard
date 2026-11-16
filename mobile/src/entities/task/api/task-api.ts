import type { PageDto } from '@/shared/api'
import { apiClient } from '@/shared/api'

import type {
  ActiveTaskSummaryReadDto,
  TaskEventListReadDto,
  TaskEventListRequest,
  TaskListItemReadDto,
  TaskListRequest,
  TaskReadDto,
} from './contracts'

function taskPath(taskId: string, suffix = ''): string {
  return `tasks/${encodeURIComponent(taskId)}${suffix}`
}

export interface TaskDataSource {
  getTasks(params: TaskListRequest): Promise<PageDto<TaskListItemReadDto>>
  getTask(taskId: string): Promise<TaskReadDto>
  getActiveTask(deviceId: string): Promise<ActiveTaskSummaryReadDto | null>
  getTaskEvents(
    taskId: string,
    params: TaskEventListRequest,
  ): Promise<TaskEventListReadDto>
}

const realTaskDataSource: TaskDataSource = {
  async getTasks(params) {
    const response = await apiClient.get<PageDto<TaskListItemReadDto>>(
      'tasks',
      { params },
    )
    return response.data
  },
  async getTask(taskId) {
    const response = await apiClient.get<TaskReadDto>(taskPath(taskId))
    return response.data
  },
  async getActiveTask(deviceId) {
    const response = await apiClient.get<ActiveTaskSummaryReadDto>(
      `tasks/active/${encodeURIComponent(deviceId)}`,
    )
    return response.status === 204 ? null : response.data
  },
  async getTaskEvents(taskId, params) {
    const response = await apiClient.get<TaskEventListReadDto>(
      taskPath(taskId, '/events'),
      { params },
    )
    return response.data
  },
}

let taskDataSource = realTaskDataSource

export function configureTaskDataSource(dataSource: TaskDataSource): void {
  taskDataSource = dataSource
}

export function resetTaskDataSource(): void {
  taskDataSource = realTaskDataSource
}

export function getTasks(
  params: TaskListRequest,
): Promise<PageDto<TaskListItemReadDto>> {
  return taskDataSource.getTasks(params)
}

export function getTask(taskId: string): Promise<TaskReadDto> {
  return taskDataSource.getTask(taskId)
}

export function getActiveTask(
  deviceId: string,
): Promise<ActiveTaskSummaryReadDto | null> {
  return taskDataSource.getActiveTask(deviceId)
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

  return taskDataSource.getTaskEvents(taskId, params)
}
