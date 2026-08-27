import type { PageDto } from '@/shared/api'

import type {
  ActiveTaskSummaryReadDto,
  TaskEventListReadDto,
  TaskEventReadDto,
  TaskListItemReadDto,
  TaskListRequest,
  TaskReadDto,
  TaskStatusDto,
} from './contracts'
import type { TaskDataSource } from './task-api'

const VISUAL_DEVICE_IDS = {
  operations: 'visual-device-operations',
  support: 'visual-device-support',
  marketing: 'visual-device-marketing',
  service: 'visual-device-service',
  data: 'visual-device-data',
} as const

export const VISUAL_TASK_IDS = {
  running: 'visual-task-running',
  success: 'visual-task-success',
  failed: 'visual-task-failed',
  pending: 'visual-task-pending',
  lost: 'visual-task-lost',
} as const

function minutesAgo(minutes: number): string {
  return new Date(Date.now() - minutes * 60_000).toISOString()
}

function createVisualTaskListItems(): TaskListItemReadDto[] {
  return [
    {
      task_id: VISUAL_TASK_IDS.running,
      target_device_id: VISUAL_DEVICE_IDS.operations,
      device_display_name: '运营',
      skill_id: 'visual-sync-orders',
      skill_display_name: '订单同步',
      execution_display_name: '订单同步',
      status: 'running',
      progress: { current: 3, total: 5 },
      current_message: '正在处理 HuanYu 店铺',
      started_at: minutesAgo(2),
      finished_at: null,
      created_at: minutesAgo(3),
    },
    {
      task_id: VISUAL_TASK_IDS.success,
      target_device_id: VISUAL_DEVICE_IDS.support,
      device_display_name: '售后',
      skill_id: 'visual-close-tickets',
      skill_display_name: '工单归档',
      execution_display_name: '售后工单归档',
      status: 'success',
      progress: null,
      current_message: '已完成 24 个售后工单归档',
      started_at: minutesAgo(22),
      finished_at: minutesAgo(16),
      created_at: minutesAgo(23),
    },
    {
      task_id: VISUAL_TASK_IDS.failed,
      target_device_id: VISUAL_DEVICE_IDS.marketing,
      device_display_name: '营销',
      skill_id: 'visual-product-audit',
      skill_display_name: '商品巡检',
      execution_display_name: '商品状态巡检',
      status: 'failed',
      progress: { current: 8, total: 12 },
      current_message: '检查商品发布状态时发现账号会话不可用，已停止本次执行',
      started_at: minutesAgo(42),
      finished_at: minutesAgo(38),
      created_at: minutesAgo(43),
    },
    {
      task_id: VISUAL_TASK_IDS.pending,
      target_device_id: VISUAL_DEVICE_IDS.service,
      device_display_name: '客服',
      skill_id: 'visual-assets-sync',
      skill_display_name: '素材同步',
      execution_display_name: '营销素材同步',
      status: 'pending',
      progress: null,
      current_message: '等待设备领取',
      started_at: null,
      finished_at: null,
      created_at: minutesAgo(58),
    },
    {
      task_id: VISUAL_TASK_IDS.lost,
      target_device_id: VISUAL_DEVICE_IDS.data,
      device_display_name: '数据中心',
      skill_id: 'visual-report',
      skill_display_name: '报表汇总',
      execution_display_name: '数据报表汇总',
      status: 'lost',
      progress: null,
      current_message: null,
      started_at: minutesAgo(82),
      finished_at: minutesAgo(76),
      created_at: minutesAgo(83),
    },
  ]
}

function taskResult(status: TaskStatusDto): Record<string, unknown> | null {
  return status === 'success' ? { summary: '已归档 24 个售后工单' } : null
}

function createVisualTaskDetails(): TaskReadDto[] {
  return createVisualTaskListItems().map((task) => ({
    task_id: task.task_id,
    target_device_id: task.target_device_id,
    shop_ids: ['visual-shop-1'],
    asset_ids: [],
    skill_id: task.skill_id,
    execution_display_name: task.execution_display_name,
    status: task.status,
    input: {},
    result: taskResult(task.status),
    error_code:
      task.status === 'failed'
        ? 'PROVIDER_SESSION_UNAVAILABLE'
        : task.status === 'lost'
          ? 'WORKER_CONNECTION_LOST'
          : null,
    error_message:
      task.status === 'failed'
        ? '账号会话不可用'
        : task.status === 'lost'
          ? '设备连接已中断'
          : null,
    lease_until: task.status === 'running' ? minutesAgo(-3) : null,
    started_at: task.started_at,
    finished_at: task.finished_at,
    runtime_events_purged_at: null,
    created_at: task.created_at,
    updated_at: task.finished_at ?? minutesAgo(0),
  }))
}

function createEvent(
  taskId: string,
  seq: number,
  eventType: TaskEventReadDto['event_type'],
  message: string,
  metadata: Record<string, unknown> = {},
): TaskEventReadDto {
  const eventAt = minutesAgo(Math.max(0, 4 - seq))
  return {
    event_id: `${taskId}-event-${seq}`,
    task_id: taskId,
    seq,
    event_type: eventType,
    level: eventType === 'failed' ? 'error' : 'info',
    message,
    event_at: eventAt,
    metadata,
    created_at: eventAt,
  }
}

function createTaskEvents(taskId: string): TaskEventReadDto[] {
  const detail = requireVisualTask(taskId)
  if (detail.status === 'pending') return []
  if (detail.status === 'running') {
    return [
      createEvent(taskId, 1, 'status', '任务开始执行'),
      createEvent(taskId, 2, 'log', '正在读取店铺订单'),
      createEvent(taskId, 3, 'progress', '正在处理 HuanYu 店铺', {
        current: 3,
        total: 5,
      }),
    ]
  }
  if (detail.status === 'success') {
    return [
      createEvent(taskId, 1, 'status', '任务开始执行'),
      createEvent(taskId, 2, 'progress', '工单归档完成', {
        current: 24,
        total: 24,
      }),
      createEvent(taskId, 3, 'completed', '任务执行成功'),
    ]
  }
  return [
    createEvent(taskId, 1, 'status', '任务开始执行'),
    createEvent(taskId, 2, 'failed', detail.error_message ?? '任务执行失败'),
  ]
}

function requireVisualTask(taskId: string): TaskReadDto {
  const task = createVisualTaskDetails().find(
    (candidate) => candidate.task_id === taskId,
  )
  if (!task) throw new Error('Visual task fixture not found')
  return task
}

function matchesTaskRequest(
  task: TaskListItemReadDto,
  request: TaskListRequest,
): boolean {
  if (request.status && task.status !== request.status) return false
  if (request.device_id && task.target_device_id !== request.device_id)
    return false
  if (request.created_from && task.created_at < request.created_from)
    return false
  if (request.created_to && task.created_at >= request.created_to) return false
  if (!request.search) return true
  const search = request.search.trim().toLocaleLowerCase()
  return [
    task.execution_display_name,
    task.skill_display_name,
    task.device_display_name,
  ].some((value) => value?.toLocaleLowerCase().includes(search))
}

function listTaskEvents(
  taskId: string,
  params: Parameters<TaskDataSource['getTaskEvents']>[1],
): TaskEventListReadDto {
  const events = createTaskEvents(taskId)
  const limit = params.limit ?? 100
  let items: TaskEventReadDto[]
  if (params.after_seq !== undefined) {
    items = events
      .filter((event) => event.seq > params.after_seq!)
      .slice(0, limit)
  } else if (params.before_seq !== undefined) {
    items = events
      .filter((event) => event.seq < params.before_seq!)
      .slice(-limit)
  } else {
    items = events.slice(-limit)
  }

  const firstSequence = items[0]?.seq ?? null
  const hasMoreBefore = Boolean(
    firstSequence !== null && events.some((event) => event.seq < firstSequence),
  )
  const fallbackAfter = params.after_seq ?? events.at(-1)?.seq ?? 0
  return {
    task_id: taskId,
    after_seq: params.after_seq ?? null,
    before_seq: params.before_seq ?? null,
    next_after_seq: items.at(-1)?.seq ?? fallbackAfter,
    next_before_seq: hasMoreBefore ? firstSequence : null,
    has_more_before: hasMoreBefore,
    items,
  }
}

export const visualMockTaskDataSource: TaskDataSource = {
  async getTasks(params): Promise<PageDto<TaskListItemReadDto>> {
    const filtered = createVisualTaskListItems().filter((task) =>
      matchesTaskRequest(task, params),
    )
    const start = (params.page - 1) * params.page_size
    return {
      items: filtered.slice(start, start + params.page_size),
      total: filtered.length,
      page: params.page,
      page_size: params.page_size,
    }
  },
  async getTask(taskId) {
    return requireVisualTask(taskId)
  },
  async getActiveTask(deviceId): Promise<ActiveTaskSummaryReadDto | null> {
    if (deviceId !== VISUAL_DEVICE_IDS.operations) return null
    const task = createVisualTaskListItems()[0]!
    const events = createTaskEvents(task.task_id)
    return {
      task_id: task.task_id,
      target_device_id: task.target_device_id,
      skill_id: task.skill_id,
      execution_display_name: task.execution_display_name,
      status: 'running',
      started_at: task.started_at,
      created_at: task.created_at,
      latest_event: events.at(-1) ?? null,
    }
  },
  async getTaskEvents(taskId, params) {
    requireVisualTask(taskId)
    return listTaskEvents(taskId, params)
  },
}
