import { httpClient, type PageDto } from '@/shared/api'

import type {
  ScheduleCreateDto,
  ScheduleListItemReadDto,
  ScheduleReadDto,
  ScheduleRunReadDto,
  ScheduleUpdateDto,
} from './contracts'

export interface ScheduleListApiParams {
  page: number
  pageSize: number
  enabled: boolean | null
  deviceId: string | null
  search: string
  occurrenceDate: string | null
  viewTimezone: string | null
}

export const scheduleApi = {
  async list(
    params: ScheduleListApiParams,
  ): Promise<PageDto<ScheduleListItemReadDto>> {
    const response = await httpClient.get<PageDto<ScheduleListItemReadDto>>(
      '/api/v1/schedules',
      {
        params: {
          page: params.page,
          page_size: params.pageSize,
          enabled: params.enabled ?? undefined,
          device_id: params.deviceId || undefined,
          search: params.search.trim() || undefined,
          occurrence_date: params.occurrenceDate ?? undefined,
          view_timezone: params.viewTimezone ?? undefined,
        },
      },
    )
    return response.data
  },

  async get(scheduleId: string): Promise<ScheduleReadDto> {
    const response = await httpClient.get<ScheduleReadDto>(
      `/api/v1/schedules/${scheduleId}`,
    )
    return response.data
  },

  async create(data: ScheduleCreateDto): Promise<ScheduleReadDto> {
    const response = await httpClient.post<ScheduleReadDto>(
      '/api/v1/schedules',
      data,
    )
    return response.data
  },

  async update(
    scheduleId: string,
    data: ScheduleUpdateDto,
  ): Promise<ScheduleReadDto> {
    const response = await httpClient.patch<ScheduleReadDto>(
      `/api/v1/schedules/${scheduleId}`,
      data,
    )
    return response.data
  },

  async remove(scheduleId: string): Promise<void> {
    await httpClient.delete(`/api/v1/schedules/${scheduleId}`)
  },

  async listRuns(
    scheduleId: string,
    page: number,
    pageSize: number,
  ): Promise<PageDto<ScheduleRunReadDto>> {
    const response = await httpClient.get<PageDto<ScheduleRunReadDto>>(
      `/api/v1/schedules/${scheduleId}/runs`,
      { params: { page, page_size: pageSize } },
    )
    return response.data
  },
}
