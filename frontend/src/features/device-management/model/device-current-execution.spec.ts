import { describe, expect, it } from 'vitest'

import type { DeviceListItemViewModel } from '@/entities/device'
import type { ActiveTaskSummaryReadDto } from '@/entities/task'

import { resolveDeviceCurrentExecution } from './device-current-execution'

const device = {
  deviceId: 'device-1',
  dataSource: 'real',
} as DeviceListItemViewModel

describe('resolveDeviceCurrentExecution', () => {
  it('maps an active task and latest event into the device summary', () => {
    const active = {
      task_id: 'task-1',
      target_device_id: 'device-1',
      skill_id: 'yingdao.test',
      execution_display_name: '执行时名称快照',
      status: 'running',
      started_at: '2026-08-22T01:00:00Z',
      created_at: '2026-08-22T00:59:00Z',
      latest_event: {
        event_id: 'event-1',
        task_id: 'task-1',
        seq: 2,
        event_type: 'status',
        level: 'worker',
        message: '测试应用已开始运行',
        event_at: '2026-08-22T01:00:02Z',
        metadata: { app_name: '后来事件中的名称' },
        created_at: '2026-08-22T01:00:02Z',
      },
    } satisfies ActiveTaskSummaryReadDto

    expect(resolveDeviceCurrentExecution(device, active, null)).toMatchObject({
      status: 'running',
      label: '执行中',
      name: '执行时名称快照',
      latestMessage: '测试应用已开始运行',
      taskId: 'task-1',
    })
  })

  it('shows a real device without an active task as idle', () => {
    expect(resolveDeviceCurrentExecution(device, null, null)).toMatchObject({
      status: 'idle',
      label: '空闲',
      taskId: null,
    })
  })

  it('uses the event application name for a legacy generic Yingdao snapshot', () => {
    const active = {
      task_id: 'task-legacy',
      target_device_id: 'device-1',
      skill_id: 'yingdao.app.run',
      execution_display_name: 'yingdao.app.run',
      status: 'running',
      started_at: '2026-08-22T01:00:00Z',
      created_at: '2026-08-22T00:59:00Z',
      latest_event: {
        event_id: 'event-legacy',
        task_id: 'task-legacy',
        seq: 2,
        event_type: 'status',
        level: 'worker',
        message: '应用已开始运行',
        event_at: '2026-08-22T01:00:02Z',
        metadata: { app_name: '原子模式单店模式' },
        created_at: '2026-08-22T01:00:02Z',
      },
    } satisfies ActiveTaskSummaryReadDto

    expect(resolveDeviceCurrentExecution(device, active, null).name).toBe(
      '原子模式单店模式',
    )
  })
})
