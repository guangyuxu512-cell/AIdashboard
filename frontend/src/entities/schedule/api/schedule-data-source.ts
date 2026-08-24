import { apiMode, type ApiMode, type PageResult } from '@/shared/api'

import {
  SCHEDULE_LIST_FIXTURE,
  scheduleFixtureToDetail,
} from '../fixtures/schedule-list.fixture'
import type {
  ScheduleDetailViewModel,
  ScheduleListFilters,
  ScheduleListItemViewModel,
  ScheduleRunViewModel,
  ScheduleSaveInput,
} from '../model/types'
import type {
  ScheduleCreateDto,
  ScheduleReadDto,
  ScheduleUpdateDto,
} from './contracts'
import { scheduleApi } from './schedule-api'
import {
  mapScheduleDetailDto,
  mapScheduleListItemDto,
  mapScheduleRunDto,
} from './schedule-mapper'

export interface ScheduleListParams {
  page: number
  pageSize: number
  filters: ScheduleListFilters
}

export interface ScheduleDataSource {
  readonly mode: ApiMode
  list(
    params: ScheduleListParams,
  ): Promise<PageResult<ScheduleListItemViewModel>>
  get(scheduleId: string): Promise<ScheduleDetailViewModel>
  create(input: ScheduleSaveInput): Promise<ScheduleDetailViewModel>
  update(
    scheduleId: string,
    input: Partial<ScheduleSaveInput>,
  ): Promise<ScheduleDetailViewModel>
  remove(scheduleId: string): Promise<void>
  listRuns(
    scheduleId: string,
    page: number,
    pageSize: number,
    timezone: string,
  ): Promise<PageResult<ScheduleRunViewModel>>
}

function toCreateDto(input: ScheduleSaveInput): ScheduleCreateDto {
  return {
    name: input.name,
    target_device_id: input.deviceId,
    application_id: input.applicationId,
    parameters: input.parameters,
    schedule_type: input.scheduleType,
    local_time: input.localTime,
    timezone: input.timezone,
    enabled: input.enabled,
  }
}

function toUpdateDto(input: Partial<ScheduleSaveInput>): ScheduleUpdateDto {
  return {
    ...(input.name !== undefined ? { name: input.name } : {}),
    ...(input.deviceId !== undefined
      ? { target_device_id: input.deviceId }
      : {}),
    ...(input.applicationId !== undefined
      ? { application_id: input.applicationId }
      : {}),
    ...(input.parameters !== undefined ? { parameters: input.parameters } : {}),
    ...(input.scheduleType !== undefined
      ? { schedule_type: input.scheduleType }
      : {}),
    ...(input.localTime !== undefined ? { local_time: input.localTime } : {}),
    ...(input.timezone !== undefined ? { timezone: input.timezone } : {}),
    ...(input.enabled !== undefined ? { enabled: input.enabled } : {}),
  }
}

function createMockScheduleDataSource(): ScheduleDataSource {
  const rows: ScheduleReadDto[] = SCHEDULE_LIST_FIXTURE.map((item) =>
    scheduleFixtureToDetail(structuredClone(item)),
  )

  function requireRow(scheduleId: string): ScheduleReadDto {
    const row = rows.find((item) => item.schedule_id === scheduleId)
    if (!row) throw new Error('定时计划不存在')
    return row
  }

  return {
    mode: 'mock',
    async list(params) {
      const search = params.filters.search.trim().toLocaleLowerCase()
      const filtered = rows.filter(
        (item) =>
          (params.filters.enabled === null ||
            item.enabled === params.filters.enabled) &&
          (!params.filters.deviceId ||
            item.target_device_id === params.filters.deviceId) &&
          (!search ||
            [item.name, item.execution_display_name, item.schedule_id].some(
              (value) => value.toLocaleLowerCase().includes(search),
            )),
      )
      const start = (params.page - 1) * params.pageSize
      return {
        items: filtered
          .slice(start, start + params.pageSize)
          .map(mapScheduleListItemDto),
        total: filtered.length,
        page: params.page,
        pageSize: params.pageSize,
      }
    },
    async get(scheduleId) {
      return mapScheduleDetailDto(structuredClone(requireRow(scheduleId)))
    },
    async create(input) {
      const now = new Date().toISOString()
      const row: ScheduleReadDto = {
        ...toCreateDto(input),
        schedule_id: crypto.randomUUID(),
        device_display_name: input.deviceId,
        skill_id: 'yingdao.app.run',
        execution_display_name: input.applicationId,
        next_run_at: input.enabled ? now : null,
        latest_run: null,
        created_at: now,
        updated_at: now,
      }
      rows.unshift(row)
      return mapScheduleDetailDto(structuredClone(row))
    },
    async update(scheduleId, input) {
      const row = requireRow(scheduleId)
      const dto = toUpdateDto(input)
      if (dto.name !== undefined) row.name = dto.name
      if (dto.target_device_id !== undefined)
        row.target_device_id = dto.target_device_id
      if (dto.application_id !== undefined) {
        row.application_id = dto.application_id
        row.execution_display_name = dto.application_id
      }
      if (dto.parameters !== undefined) row.parameters = dto.parameters
      if (dto.schedule_type !== undefined) row.schedule_type = dto.schedule_type
      if (dto.local_time !== undefined) row.local_time = dto.local_time
      if (dto.timezone !== undefined) row.timezone = dto.timezone
      if (dto.enabled !== undefined) {
        row.enabled = dto.enabled
        row.next_run_at = dto.enabled ? new Date().toISOString() : null
      }
      row.updated_at = new Date().toISOString()
      return mapScheduleDetailDto(structuredClone(row))
    },
    async remove(scheduleId) {
      const index = rows.findIndex((item) => item.schedule_id === scheduleId)
      if (index < 0) throw new Error('定时计划不存在')
      rows.splice(index, 1)
    },
    async listRuns(scheduleId, page, pageSize, timezone) {
      const row = requireRow(scheduleId)
      const items = row.latest_run
        ? [mapScheduleRunDto(row.latest_run, timezone)]
        : []
      return { items, total: items.length, page, pageSize }
    },
  }
}

const realScheduleDataSource: ScheduleDataSource = {
  mode: 'real',
  async list(params) {
    const page = await scheduleApi.list({
      page: params.page,
      pageSize: params.pageSize,
      enabled: params.filters.enabled,
      deviceId: params.filters.deviceId,
      search: params.filters.search,
    })
    return {
      items: page.items.map(mapScheduleListItemDto),
      total: page.total,
      page: page.page,
      pageSize: page.page_size,
    }
  },
  async get(scheduleId) {
    return mapScheduleDetailDto(await scheduleApi.get(scheduleId))
  },
  async create(input) {
    return mapScheduleDetailDto(await scheduleApi.create(toCreateDto(input)))
  },
  async update(scheduleId, input) {
    return mapScheduleDetailDto(
      await scheduleApi.update(scheduleId, toUpdateDto(input)),
    )
  },
  remove: scheduleApi.remove,
  async listRuns(scheduleId, page, pageSize, timezone) {
    const result = await scheduleApi.listRuns(scheduleId, page, pageSize)
    return {
      items: result.items.map((item) => mapScheduleRunDto(item, timezone)),
      total: result.total,
      page: result.page,
      pageSize: result.page_size,
    }
  },
}

export function createScheduleDataSource(mode: ApiMode): ScheduleDataSource {
  return mode === 'real'
    ? realScheduleDataSource
    : createMockScheduleDataSource()
}

export const scheduleDataSource = createScheduleDataSource(apiMode)
