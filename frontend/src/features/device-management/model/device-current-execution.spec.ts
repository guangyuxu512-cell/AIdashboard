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
        metadata: { app_name: '无副作用测试应用' },
        created_at: '2026-08-22T01:00:02Z',
      },
    } satisfies ActiveTaskSummaryReadDto

    expect(resolveDeviceCurrentExecution(device, active, null)).toMatchObject({
      status: 'running',
      label: '执行中',
      name: '无副作用测试应用',
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
})
