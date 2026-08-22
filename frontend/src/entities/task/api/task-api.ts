import { httpClient } from '@/shared/api'

import type {
  ActiveTaskSummaryReadDto,
  TaskCreateDto,
  TaskEventListReadDto,
  TaskReadDto,
} from './contracts'

export const taskApi = {
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
