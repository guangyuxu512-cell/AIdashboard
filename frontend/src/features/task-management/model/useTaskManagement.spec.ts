import dayjs from 'dayjs'
import { describe, expect, it } from 'vitest'

import {
  createDefaultTaskFilters,
  DEFAULT_TASK_DATE_PRESET,
  resolveTaskListFilters,
} from './useTaskManagement'

const now = new Date('2026-08-24T15:30:00+08:00')
const today = dayjs(now).startOf('day')

describe('Task Center date filters', () => {
  it('defaults and resets to the latest seven calendar days', () => {
    const defaults = createDefaultTaskFilters()
    const resolved = resolveTaskListFilters(defaults, now)

    expect(defaults).toEqual({
      status: null,
      deviceId: null,
      search: '',
      datePreset: DEFAULT_TASK_DATE_PRESET,
      customDateRange: null,
    })
    expect(resolved.createdFrom).toBe(today.subtract(6, 'day').toISOString())
    expect(resolved.createdTo).toBe(today.add(1, 'day').toISOString())
  })

  it.each([
    ['today', today, today.add(1, 'day')],
    ['yesterday', today.subtract(1, 'day'), today],
    ['last30Days', today.subtract(29, 'day'), today.add(1, 'day')],
  ] as const)(
    'resolves %s as an absolute half-open range',
    (preset, from, to) => {
      const resolved = resolveTaskListFilters(
        { ...createDefaultTaskFilters(), datePreset: preset },
        now,
      )

      expect(resolved.createdFrom).toBe(from.toISOString())
      expect(resolved.createdTo).toBe(to.toISOString())
    },
  )

  it('converts a custom local date range to inclusive/exclusive instants', () => {
    const start = dayjs('2026-08-02').valueOf()
    const end = dayjs('2026-08-05').valueOf()

    const resolved = resolveTaskListFilters(
      {
        status: 'failed',
        deviceId: 'device-1',
        search: 'fixture',
        datePreset: 'custom',
        customDateRange: [start, end],
      },
      now,
    )

    expect(resolved).toEqual({
      status: 'failed',
      deviceId: 'device-1',
      search: 'fixture',
      createdFrom: dayjs(start).startOf('day').toISOString(),
      createdTo: dayjs(end).startOf('day').add(1, 'day').toISOString(),
    })
  })

  it('removes both boundaries only for all-time', () => {
    const resolved = resolveTaskListFilters(
      { ...createDefaultTaskFilters(), datePreset: 'all' },
      now,
    )

    expect(resolved.createdFrom).toBeNull()
    expect(resolved.createdTo).toBeNull()
  })
})
