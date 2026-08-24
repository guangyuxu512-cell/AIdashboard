import { describe, expect, it } from 'vitest'

import { SCHEDULE_LIST_FIXTURE } from '../fixtures/schedule-list.fixture'
import { mapScheduleListItemDto } from './schedule-mapper'

describe('schedule mapper', () => {
  it('maps daily rule, timezone and latest Task status', () => {
    const result = mapScheduleListItemDto(SCHEDULE_LIST_FIXTURE[0]!)

    expect(result.triggerRuleDisplay).toBe('每天 09:30')
    expect(result.timezone).toBe('Asia/Shanghai')
    expect(result.nextRunAtDisplay).toBe('2026-08-25 09:30')
    expect(result.createdAtDisplay).toBe('2026-08-20 11:00')
    expect(result.updatedAtDisplay).toBe('2026-08-24 09:30')
    expect(result.latestRun?.taskStatus).toBe('success')
  })

  it('keeps disabled schedules without a next run as a normal value', () => {
    const result = mapScheduleListItemDto(SCHEDULE_LIST_FIXTURE[1]!)

    expect(result.enabled).toBe(false)
    expect(result.nextRunAtDisplay).toBe('—')
    expect(result.latestRun).toBeNull()
  })
})
