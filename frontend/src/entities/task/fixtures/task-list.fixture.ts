import type {
  TaskEventReadDto,
  TaskListItemReadDto,
  TaskReadDto,
} from '../api/contracts'

export const TASK_FIXTURE_IDS = {
  runningYingdao: '10000000-0000-4000-8000-000000000001',
  pending: '10000000-0000-4000-8000-000000000002',
  runningProgress: '10000000-0000-4000-8000-000000000003',
  success: '10000000-0000-4000-8000-000000000004',
  failed: '10000000-0000-4000-8000-000000000005',
  lost: '10000000-0000-4000-8000-000000000006',
  oldSuccess: '10000000-0000-4000-8000-000000000007',
} as const

export const TASK_LIST_FIXTURE: TaskListItemReadDto[] = [
  {
    task_id: TASK_FIXTURE_IDS.runningYingdao,
    target_device_id: 'device-fixture-001',
    device_display_name: '杭州-运营机-01',
    skill_id: 'yingdao.app.run',
    skill_display_name: '运行影刀应用',
    execution_display_name: '原子模式单店模式',
    status: 'running',
    progress: null,
    current_message: '正在运行影刀应用',
    started_at: '2026-08-24T05:22:10+08:00',
    finished_at: null,
    created_at: '2026-08-24T05:22:08+08:00',
  },
  {
    task_id: TASK_FIXTURE_IDS.pending,
    target_device_id: 'device-fixture-001',
    device_display_name: '杭州-运营机-01',
    skill_id: 'yingdao.app.run',
    skill_display_name: '运行影刀应用',
    execution_display_name: '拼多多工单处理',
    status: 'pending',
    progress: null,
    current_message: null,
    started_at: null,
    finished_at: null,
    created_at: '2026-08-24T05:21:20+08:00',
  },
  {
    task_id: TASK_FIXTURE_IDS.runningProgress,
    target_device_id: 'device-fixture-002',
    device_display_name: '上海-直播机-02',
    skill_id: 'system.sleep',
    skill_display_name: '系统等待',
    execution_display_name: 'Python 进度闭环验证',
    status: 'running',
    progress: { current: 3, total: 10 },
    current_message: '正在处理第 3 项',
    started_at: '2026-08-24T05:21:03+08:00',
    finished_at: null,
    created_at: '2026-08-24T05:21:01+08:00',
  },
  {
    task_id: TASK_FIXTURE_IDS.success,
    target_device_id: 'device-fixture-003',
    device_display_name: '深圳-工作站-03',
    skill_id: 'system.echo',
    skill_display_name: '系统回声',
    execution_display_name: '系统回声验证',
    status: 'success',
    progress: { current: 100, total: 100 },
    current_message: '执行完成',
    started_at: '2026-08-24T05:10:11+08:00',
    finished_at: '2026-08-24T05:10:14+08:00',
    created_at: '2026-08-24T05:10:09+08:00',
  },
  {
    task_id: TASK_FIXTURE_IDS.failed,
    target_device_id: 'device-fixture-005',
    device_display_name: '北京-运营机-05',
    skill_id: 'yingdao.test',
    skill_display_name: '影刀无副作用测试',
    execution_display_name: '影刀无副作用测试',
    status: 'failed',
    progress: null,
    current_message: '影刀运行时返回失败',
    started_at: '2026-08-24T04:58:00+08:00',
    finished_at: '2026-08-24T04:58:08+08:00',
    created_at: '2026-08-24T04:57:58+08:00',
  },
  {
    task_id: TASK_FIXTURE_IDS.lost,
    target_device_id: 'device-fixture-004',
    device_display_name: '杭州-备用机-04',
    skill_id: 'system.sleep',
    skill_display_name: '系统等待',
    execution_display_name: 'Worker 失联验证',
    status: 'lost',
    progress: null,
    current_message: 'Worker 租约到期，任务已丢失',
    started_at: '2026-08-24T04:40:00+08:00',
    finished_at: '2026-08-24T04:41:00+08:00',
    created_at: '2026-08-24T04:39:58+08:00',
  },
  {
    task_id: TASK_FIXTURE_IDS.oldSuccess,
    target_device_id: 'device-fixture-003',
    device_display_name: '深圳-工作站-03',
    skill_id: 'system.echo',
    skill_display_name: '系统回声',
    execution_display_name: '历史审计任务',
    status: 'success',
    progress: null,
    current_message: '历史执行完成',
    started_at: '2026-07-01T05:10:11+08:00',
    finished_at: '2026-07-01T05:10:14+08:00',
    created_at: '2026-07-01T05:10:09+08:00',
  },
]

export function taskFixtureToDetail(item: TaskListItemReadDto): TaskReadDto {
  return {
    task_id: item.task_id,
    target_device_id: item.target_device_id,
    shop_ids: [],
    skill_id: item.skill_id,
    execution_display_name: item.execution_display_name,
    status: item.status,
    input: {},
    result: item.status === 'success' ? { ok: true } : null,
    error_code:
      item.status === 'failed'
        ? 'RUNTIME_FAILED'
        : item.status === 'lost'
          ? 'WORKER_LEASE_EXPIRED'
          : null,
    error_message:
      item.status === 'failed' || item.status === 'lost'
        ? item.current_message
        : null,
    lease_until: item.status === 'running' ? '2026-08-24T06:00:00+08:00' : null,
    started_at: item.started_at,
    finished_at: item.finished_at,
    runtime_events_purged_at:
      item.task_id === TASK_FIXTURE_IDS.failed ||
      item.task_id === TASK_FIXTURE_IDS.lost
        ? '2026-08-24T06:30:00+08:00'
        : null,
    created_at: item.created_at,
    updated_at: item.finished_at ?? item.started_at ?? item.created_at,
  }
}

function event(
  taskId: string,
  seq: number,
  eventType: TaskEventReadDto['event_type'],
  message: string,
  metadata: Record<string, unknown> = {},
): TaskEventReadDto {
  const eventAt = new Date(
    Date.parse('2026-08-24T05:22:00+08:00') + seq * 1_000,
  ).toISOString()
  return {
    event_id: `${taskId}:event:${seq}`,
    task_id: taskId,
    seq,
    event_type: eventType,
    level: eventType === 'log' ? 'INFO' : 'worker',
    message,
    event_at: eventAt,
    metadata,
    created_at: eventAt,
  }
}

export const TASK_EVENT_FIXTURE: Record<string, TaskEventReadDto[]> = {
  [TASK_FIXTURE_IDS.runningYingdao]: [
    event(TASK_FIXTURE_IDS.runningYingdao, 1, 'status', '正在启动影刀运行时', {
      provider: 'yingdao',
      app_name: '原子模式单店模式',
    }),
    event(TASK_FIXTURE_IDS.runningYingdao, 2, 'log', '正在运行影刀应用'),
  ],
  [TASK_FIXTURE_IDS.pending]: [],
  [TASK_FIXTURE_IDS.runningProgress]: [
    event(TASK_FIXTURE_IDS.runningProgress, 1, 'status', '开始执行'),
    event(TASK_FIXTURE_IDS.runningProgress, 2, 'progress', '正在处理第 3 项', {
      provider: 'python',
      current: 3,
      total: 10,
    }),
  ],
  [TASK_FIXTURE_IDS.success]: Array.from({ length: 205 }, (_, index) =>
    event(
      TASK_FIXTURE_IDS.success,
      index + 1,
      index === 204 ? 'completed' : 'log',
      index === 204 ? '执行完成' : `历史日志 ${index + 1}`,
    ),
  ),
  [TASK_FIXTURE_IDS.failed]: [],
  [TASK_FIXTURE_IDS.lost]: [
    event(TASK_FIXTURE_IDS.lost, 1, 'status', 'Worker 已领取任务'),
  ],
  [TASK_FIXTURE_IDS.oldSuccess]: [],
}
