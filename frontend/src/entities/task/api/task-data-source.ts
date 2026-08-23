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
    afterSeq: number,
    limit?: number,
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
      const filtered = rows.filter(
        (task) =>
          (!params.filters.status || task.status === params.filters.status) &&
          (!params.filters.deviceId ||
            task.target_device_id === params.filters.deviceId) &&
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
    async listEvents(taskId, afterSeq, limit = 100) {
      getDetail(taskId)
      const items = (TASK_EVENT_FIXTURE[taskId] ?? [])
        .filter((item) => item.seq > afterSeq)
        .slice(0, limit)
      return {
        task_id: taskId,
        after_seq: afterSeq,
        next_after_seq: items.at(-1)?.seq ?? afterSeq,
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
