import { describe, expect, it } from 'vitest'

import { createScheduleDataSource } from './schedule-data-source'

describe('mock schedule data source', () => {
  it('filters, creates, toggles and archives schedules', async () => {
    const source = createScheduleDataSource('mock')
    const enabled = await source.list({
      page: 1,
      pageSize: 10,
      filters: {
        enabled: true,
        deviceId: null,
        search: '',
        occurrenceDate: null,
        viewTimezone: null,
      },
    })
    expect(enabled.items).toHaveLength(1)

    const selectedDate = await source.list({
      page: 1,
      pageSize: 10,
      filters: {
        enabled: null,
        deviceId: null,
        search: '',
        occurrenceDate: '2026-08-25',
        viewTimezone: 'Asia/Shanghai',
      },
    })
    expect(selectedDate.items.map((item) => item.scheduleId)).toEqual([
      '60000000-0000-4000-8000-000000000001',
    ])

    const created = await source.create({
      name: '测试计划',
      deviceId: 'device-fixture-001',
      shopIds: ['shop-fixture-001'],
      executionType: 'yingdao_application',
      applicationId: 'app-fixture-product-publish-1',
      parameterPresetId: null,
      skillId: null,
      parameters: {},
      scheduleType: 'daily',
      localTime: '10:30',
      timezone: 'Asia/Shanghai',
      localDate: null,
      weekdays: [],
      enabled: true,
    })
    expect(created.triggerRuleDisplay).toBe('每天 10:30')

    const disabled = await source.update(created.scheduleId, { enabled: false })
    expect(disabled.enabled).toBe(false)
    expect(disabled.nextRunAt).toBeNull()

    await source.remove(created.scheduleId)
    await expect(source.get(created.scheduleId)).rejects.toThrow(
      '定时计划不存在',
    )
  })
})
