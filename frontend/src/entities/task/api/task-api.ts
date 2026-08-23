import { httpClient } from '@/shared/api'
import type { PageDto } from '@/shared/api'

import type {
  ActiveTaskSummaryReadDto,
  TaskCreateDto,
  TaskEventListReadDto,
  TaskListItemReadDto,
  TaskReadDto,
} from './contracts'

export interface TaskListApiParams {
  page: number
  pageSize: number
  status: string | null
  deviceId: string | null
  search: string
}

export const taskApi = {
  async list(params: TaskListApiParams): Promise<PageDto<TaskListItemReadDto>> {
    const response = await httpClient.get<PageDto<TaskListItemReadDto>>(
      '/api/v1/tasks',
      {
        params: {
          page: params.page,
          page_size: params.pageSize,
          status: params.status || undefined,
          device_id: params.deviceId || undefined,
          search: params.search.trim() || undefined,
        },
      },
    )
    return response.data
  },

  async create(data: TaskCreateDto): Promise<TaskReadDto> {
    const response = await httpClient.post<TaskReadDto>('/api/v1/tasks', data)
    return response.data
  },

  async get(taskId: string): Promise<TaskReadDto> {
    const response = await httpClient.get<TaskReadDto>(
      `/api/v1/tasks/${taskId}`,
    )
    return response.data
  },

  async getActive(deviceId: string): Promise<ActiveTaskSummaryReadDto | null> {
    const response = await httpClient.get<ActiveTaskSummaryReadDto>(
      `/api/v1/tasks/active/${deviceId}`,
      { validateStatus: (status) => status === 200 || status === 204 },
    )
    return response.status === 204 ? null : response.data
  },

  async listEvents(
    taskId: string,
    afterSeq: number,
    limit = 100,
  ): Promise<TaskEventListReadDto> {
    const response = await httpClient.get<TaskEventListReadDto>(
      `/api/v1/tasks/${taskId}/events`,
      { params: { after_seq: afterSeq, limit } },
    )
    return response.data
  },
}
