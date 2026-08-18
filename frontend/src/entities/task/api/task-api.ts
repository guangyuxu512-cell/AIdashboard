import { httpClient } from '@/shared/api'

import type { TaskCreateDto, TaskReadDto } from './contracts'

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
}
