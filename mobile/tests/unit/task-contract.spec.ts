import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  getTaskEvents,
  getTasks,
  mapTaskListItem,
  resolveExecutionName,
  TASK_STATUSES,
  TASK_STATUS_META,
  type TaskListItemReadDto,
} from '@/entities/task'
import { apiClient } from '@/shared/api'

const taskListDto: TaskListItemReadDto = {
  task_id: 'task-1',
  target_device_id: 'device-1',
  device_display_name: '仓库手机',
  skill_id: 'sync-orders',
  skill_display_name: '同步订单',
  execution_display_name: '同步近七日订单',
  status: 'running',
  progress: { current: 2, total: 10 },
  current_message: '正在读取订单',
  started_at: '2026-08-26T01:00:00Z',
  finished_at: null,
  created_at: '2026-08-26T00:59:00Z',
}

describe('task contract and mapper', () => {
  afterEach(() => vi.restoreAllMocks())

  it('uses relative formal endpoints and preserves query parameters', async () => {
    const get = vi.spyOn(apiClient, 'get').mockResolvedValue({
      data: { items: [taskListDto], total: 1, page: 1, page_size: 20 },
    })
    const params = {
      page: 1,
      page_size: 20,
      status: 'running' as const,
      device_id: 'device-1',
      search: '订单',
      created_from: '2026-08-19T00:00:00.000Z',
      created_to: '2026-08-27T00:00:00.000Z',
    }

    await getTasks(params)

    expect(get).toHaveBeenCalledWith('tasks', { params })
  })

  it('enforces the event cursor and limit contract before requesting', async () => {
    const get = vi.spyOn(apiClient, 'get')

    await expect(
      getTaskEvents('task/1', { after_seq: 2, before_seq: 3 }),
    ).rejects.toThrow('不能同时')
    await expect(getTaskEvents('task-1', { limit: 201 })).rejects.toThrow(
      '1 到 200',
    )
    expect(get).not.toHaveBeenCalled()
  })

  it('uses encoded task event paths with either after_seq or before_seq', async () => {
    const get = vi.spyOn(apiClient, 'get').mockResolvedValue({
      data: {
        task_id: 'task/1',
        after_seq: 8,
        before_seq: null,
        next_after_seq: 9,
        next_before_seq: null,
        has_more_before: false,
        items: [],
      },
    })

    await getTaskEvents('task/1', { after_seq: 8, limit: 100 })
    await getTaskEvents('task/1', { before_seq: 8, limit: 50 })

    expect(get).toHaveBeenNthCalledWith(1, 'tasks/task%2F1/events', {
      params: { after_seq: 8, limit: 100 },
    })
    expect(get).toHaveBeenNthCalledWith(2, 'tasks/task%2F1/events', {
      params: { before_seq: 8, limit: 50 },
    })
  })

  it('maps DTO and follows the execution-name fallback order', () => {
    expect(mapTaskListItem(taskListDto)).toEqual(
      expect.objectContaining({
        taskId: 'task-1',
        executionName: '同步近七日订单',
        status: 'running',
      }),
    )
    expect(
      resolveExecutionName({
        execution_display_name: ' ',
        skill_display_name: '同步订单',
        skill_id: 'sync-orders',
      }),
    ).toBe('同步订单')
    expect(
      resolveExecutionName({
        execution_display_name: '',
        skill_display_name: null,
        skill_id: 'sync-orders',
      }),
    ).toBe('sync-orders')
  })

  it('owns one complete and unique Chinese status mapping', () => {
    expect(Object.keys(TASK_STATUS_META)).toEqual(TASK_STATUSES)
    expect(
      Object.fromEntries(
        TASK_STATUSES.map((status) => [status, TASK_STATUS_META[status].label]),
      ),
    ).toEqual({
      pending: '待执行',
      running: '执行中',
      success: '成功',
      failed: '失败',
      lost: '已丢失',
    })
    expect(
      new Set(TASK_STATUSES.map((status) => TASK_STATUS_META[status].label))
        .size,
    ).toBe(5)
  })
})
