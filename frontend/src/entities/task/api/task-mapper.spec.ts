import { describe, expect, it } from 'vitest'

import type { TaskListItemReadDto } from './contracts'
import { mapTaskListItemDto } from './task-mapper'

function dto(
  overrides: Partial<TaskListItemReadDto> = {},
): TaskListItemReadDto {
  return {
    task_id: 'task-1',
    target_device_id: 'device-1',
    device_display_name: 'PC-11',
    skill_id: 'system.sleep',
    skill_display_name: '系统等待',
    execution_display_name: '安全等待',
    status: 'running',
    progress: null,
    current_message: null,
    started_at: null,
    finished_at: null,
    created_at: '2026-08-24T00:00:00Z',
    ...overrides,
  }
}

describe('Task list mapper', () => {
  it('maps structured progress and keeps pending start time empty', () => {
    const item = mapTaskListItemDto(
      dto({
        status: 'pending',
        progress: { current: 3, total: 10 },
        current_message: '正在处理第 3 项',
      }),
    )

    expect(item.progressDisplay).toBe('3 / 10')
    expect(item.currentMessage).toBe('正在处理第 3 项')
    expect(item.startedAtDisplay).toBe('—')
  })

  it('uses execution, Skill display name and the shared Chinese mapping in priority order', () => {
    expect(mapTaskListItemDto(dto()).executionName).toBe('安全等待')
    expect(
      mapTaskListItemDto(dto({ execution_display_name: ' ' })).executionName,
    ).toBe('系统等待')
    expect(
      mapTaskListItemDto(
        dto({ execution_display_name: '', skill_display_name: null }),
      ).executionName,
    ).toBe('等待（测试）')
  })

  it('translates raw worker names and preserves explicit names', () => {
    expect(mapTaskListItemDto(dto({
      skill_id: 'douyin.compass_selection',
      execution_display_name: 'douyin.compass_selection',
      skill_display_name: 'douyin.compass_selection',
    })).executionName).toBe('罗盘选品')
    expect(mapTaskListItemDto(dto({
      skill_id: 'douyin.compass_selection',
      execution_display_name: 'douyin.compass_selection',
      skill_display_name: '自定义选品',
    })).executionName).toBe('自定义选品')
    expect(mapTaskListItemDto(dto({
      skill_id: 'vendor.custom',
      execution_display_name: 'vendor.custom',
      skill_display_name: null,
    })).executionName).toBe('vendor.custom')
  })
})
