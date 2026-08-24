import { apiMode, type ApiMode, type PageResult } from '@/shared/api'

import {
  TASK_EVENT_FIXTURE,
  TASK_LIST_FIXTURE,
  taskFixtureToDetail,
} from '../fixtures/task-list.fixture'
import type { TaskListFilters, TaskListItemViewModel } from '../model/types'
import type {
  ActiveTaskSummaryReadDto,
  TaskCreateDto,
  TaskEventListReadDto,
  TaskListItemReadDto,
  TaskReadDto,
} from './contracts'
import { taskApi } from './task-api'
import type { TaskEventApiParams } from './task-api'
import { mapTaskListItemDto } from './task-mapper'

export interface TaskListParams {
  page: number
  pageSize: number
  filters: TaskListFilters
}

export interface TaskDataSource {
  readonly mode: ApiMode
  list(params: TaskListParams): Promise<PageResult<TaskListItemViewModel>>
  get(taskId: string): Promise<TaskReadDto>
  getActive(deviceId: string): Promise<ActiveTaskSummaryReadDto | null>
  listEvents(
    taskId: string,
    params?: TaskEventApiParams,
  ): Promise<TaskEventListReadDto>
  create(data: TaskCreateDto): Promise<TaskReadDto>
}

function createMockTaskDataSource(): TaskDataSource {
  const rows: TaskListItemReadDto[] = TASK_LIST_FIXTURE.map((item) => ({
    ...item,
    progress: item.progress ? { ...item.progress } : null,
  }))

  function getDetail(taskId: string): TaskReadDto {
    const task = rows.find((item) => item.task_id === taskId)
    if (!task) throw new Error('任务不存在')
    return taskFixtureToDetail(task)
  }

  return {
    mode: 'mock',
    async list(params) {
      const search = params.filters.search.trim().toLocaleLowerCase()
      const createdFrom = params.filters.createdFrom
        ? Date.parse(params.filters.createdFrom)
        : null
      const createdTo = params.filters.createdTo
        ? Date.parse(params.filters.createdTo)
        : null
      const filtered = rows.filter(
        (task) =>
          (!params.filters.status || task.status === params.filters.status) &&
          (!params.filters.deviceId ||
            task.target_device_id === params.filters.deviceId) &&
          (createdFrom === null ||
            Date.parse(task.created_at) >= createdFrom) &&
          (createdTo === null || Date.parse(task.created_at) < createdTo) &&
          (!search ||
            [task.task_id, task.execution_display_name, task.skill_id].some(
              (value) => value.toLocaleLowerCase().includes(search),
            )),
      )
      const start = (params.page - 1) * params.pageSize
      return {
        items: filtered
          .slice(start, start + params.pageSize)
          .map(mapTaskListItemDto),
        total: filtered.length,
        page: params.page,
        pageSize: params.pageSize,
      }
    },
    async get(taskId) {
      return getDetail(taskId)
    },
    async getActive(deviceId) {
      const task = rows.find(
        (item) =>
          item.target_device_id === deviceId &&
          (item.status === 'pending' || item.status === 'running'),
      )
      if (!task) return null
      const events = TASK_EVENT_FIXTURE[task.task_id] ?? []
      return {
        task_id: task.task_id,
        target_device_id: task.target_device_id,
        skill_id: task.skill_id,
        execution_display_name: task.execution_display_name,
        status: task.status as 'pending' | 'running',
        started_at: task.started_at,
        created_at: task.created_at,
        latest_event: events.at(-1) ?? null,
      }
    },
    async listEvents(taskId, params = {}) {
      getDetail(taskId)
      const limit = params.limit ?? 100
      const allItems = TASK_EVENT_FIXTURE[taskId] ?? []
      if (params.afterSeq !== undefined) {
        const items = allItems
          .filter((item) => item.seq > params.afterSeq!)
          .slice(0, limit)
        return {
          task_id: taskId,
          after_seq: params.afterSeq,
          before_seq: null,
          next_after_seq: items.at(-1)?.seq ?? params.afterSeq,
          next_before_seq: null,
          has_more_before: false,
          items,
        }
      }
      const candidates = allItems.filter(
        (item) => params.beforeSeq === undefined || item.seq < params.beforeSeq,
      )
      const items = candidates.slice(-limit)
      const hasMoreBefore = candidates.length > items.length
      return {
        task_id: taskId,
        after_seq: null,
        before_seq: params.beforeSeq ?? null,
        next_after_seq: items.at(-1)?.seq ?? 0,
        next_before_seq:
          hasMoreBefore && items.length ? (items[0]?.seq ?? null) : null,
        has_more_before: hasMoreBefore,
        items,
      }
    },
    async create(data) {
      const now = new Date().toISOString()
      const taskId = crypto.randomUUID()
      const item: TaskListItemReadDto = {
        task_id: taskId,
        target_device_id: data.target_device_id,
        device_display_name: data.target_device_id,
        skill_id: data.skill_id,
        skill_display_name: null,
        execution_display_name: data.skill_id,
        status: 'pending',
        progress: null,
        current_message: null,
        started_at: null,
        finished_at: null,
        created_at: now,
      }
      rows.unshift(item)
      TASK_EVENT_FIXTURE[taskId] = []
      return taskFixtureToDetail(item)
    },
  }
}

const realTaskDataSource: TaskDataSource = {
  mode: 'real',
  async list(params) {
    const page = await taskApi.list({
      page: params.page,
      pageSize: params.pageSize,
      status: params.filters.status,
      deviceId: params.filters.deviceId,
      search: params.filters.search,
      createdFrom: params.filters.createdFrom,
      createdTo: params.filters.createdTo,
    })
    return {
      items: page.items.map(mapTaskListItemDto),
      total: page.total,
      page: page.page,
      pageSize: page.page_size,
    }
  },
  get: taskApi.get,
  getActive: taskApi.getActive,
  listEvents: taskApi.listEvents,
  create: taskApi.create,
}

export function createTaskDataSource(mode: ApiMode): TaskDataSource {
  return mode === 'real' ? realTaskDataSource : createMockTaskDataSource()
}

export const taskDataSource = createTaskDataSource(apiMode)
