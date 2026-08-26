import { describe, expect, it } from 'vitest'

import { getNextDevicePageParam } from '@/entities/device'
import {
  flattenTaskPages,
  getNextTaskPageParam,
  getTaskListRefetchInterval,
  TASK_LIST_REFRESH_INTERVAL_MS,
  toTaskListRequest,
  type TaskListPage,
} from '@/entities/task'
import {
  buildTaskListFilters,
  createDefaultTaskDateRange,
  createDefaultTaskFilterDraft,
  createTaskDateRange,
  createTaskPresetDateRange,
} from '@/features/task-center'
import { classifyInfiniteQueryError } from '@/shared/utils/infinite-query-error'

function page(pageNumber: number, ids: string[], total: number): TaskListPage {
  return {
    page: pageNumber,
    pageSize: 2,
    total,
    items: ids.map((taskId) => ({
      taskId,
      targetDeviceId: 'device-1',
      deviceDisplayName: '设备',
      skillId: 'skill-1',
      executionName: taskId,
      status: 'pending',
      progress: null,
      currentMessage: null,
      startedAt: null,
      finishedAt: null,
      createdAt: '2026-08-26T00:00:00Z',
    })),
  }
}

describe('task filters and infinite paging', () => {
  const now = new Date(2026, 7, 26, 15, 30)

  it('defaults to a local seven-calendar-day half-open range', () => {
    const range = createDefaultTaskDateRange(now)
    const draft = createDefaultTaskFilterDraft(now)

    expect(draft.datePreset).toBe('last-7-days')
    expect(range.start).toEqual(new Date(2026, 7, 20))
    expect(range.endInclusive).toEqual(new Date(2026, 7, 26))
    expect(new Date(range.createdTo)).toEqual(new Date(2026, 7, 27))
  })

  it.each([
    [
      'today',
      new Date(2026, 7, 26),
      new Date(2026, 7, 26),
      new Date(2026, 7, 27),
    ],
    [
      'yesterday',
      new Date(2026, 7, 25),
      new Date(2026, 7, 25),
      new Date(2026, 7, 26),
    ],
    [
      'last-7-days',
      new Date(2026, 7, 20),
      new Date(2026, 7, 26),
      new Date(2026, 7, 27),
    ],
    [
      'last-30-days',
      new Date(2026, 6, 28),
      new Date(2026, 7, 26),
      new Date(2026, 7, 27),
    ],
  ] as const)(
    'creates the exact %s local natural-day preset',
    (preset, start, end, exclusiveEnd) => {
      const range = createTaskPresetDateRange(preset, now)
      expect(range.start).toEqual(start)
      expect(range.endInclusive).toEqual(end)
      expect(new Date(range.createdTo)).toEqual(exclusiveEnd)
    },
  )

  it('normalizes a custom range and emits frozen snake_case params', () => {
    const dateRange = createTaskDateRange(
      new Date(2026, 6, 1, 18),
      new Date(2026, 6, 3, 20),
    )
    const filters = buildTaskListFilters(
      'failed',
      {
        search: '  订单  ',
        deviceId: 'device-8',
        deviceName: '设备八',
        datePreset: 'custom',
        dateRange: [dateRange.start, dateRange.endInclusive],
      },
      now,
    )

    expect(toTaskListRequest(filters, 3)).toEqual({
      page: 3,
      page_size: 20,
      status: 'failed',
      device_id: 'device-8',
      search: '订单',
      created_from: dateRange.createdFrom,
      created_to: dateRange.createdTo,
    })
  })

  it('omits both date parameters for all time', () => {
    const draft = createDefaultTaskFilterDraft(now)
    draft.datePreset = 'all-time'

    expect(
      toTaskListRequest(buildTaskListFilters('all', draft, now), 1),
    ).toEqual({ page: 1, page_size: 20 })
  })

  it('keeps backend page order while deduplicating task_id', () => {
    const first = page(1, ['task-1', 'task-2'], 4)
    const second = page(2, ['task-2', 'task-3'], 4)

    expect(
      flattenTaskPages([first, second]).map((task) => task.taskId),
    ).toEqual(['task-1', 'task-2', 'task-3'])
    expect(getNextTaskPageParam(first)).toBe(2)
    expect(getNextTaskPageParam(second)).toBeUndefined()
  })

  it('polls one task page and pauses after infinite scrolling', () => {
    const first = page(1, ['task-1'], 3)
    const second = page(2, ['task-2'], 3)

    expect(
      getTaskListRefetchInterval({ pages: [first], pageParams: [1] }),
    ).toBe(TASK_LIST_REFRESH_INTERVAL_MS)
    expect(
      getTaskListRefetchInterval({
        pages: [first, second],
        pageParams: [1, 2],
      }),
    ).toBe(false)
  })

  it('continues device pagination beyond the first 100 options', () => {
    expect(
      getNextDevicePageParam({
        items: Array.from({ length: 100 }, (_, index) => ({
          device_id: `device-${index}`,
          display_name: `设备 ${index}`,
          enabled: true,
          location: null,
          note: null,
          deleted_at: null,
          worker_runtime: null,
          created_at: '2026-08-26T00:00:00Z',
          updated_at: '2026-08-26T00:00:00Z',
        })),
        total: 205,
        page: 1,
        page_size: 100,
      }),
    ).toBe(2)
  })

  it('distinguishes empty-cache background errors from next-page errors', () => {
    expect(
      classifyInfiniteQueryError({
        hasSuccessfulData: true,
        isError: true,
        isFetchNextPageError: false,
      }),
    ).toBe('background')
    expect(
      classifyInfiniteQueryError({
        hasSuccessfulData: true,
        isError: true,
        isFetchNextPageError: true,
      }),
    ).toBe('next-page')
    expect(
      classifyInfiniteQueryError({
        hasSuccessfulData: false,
        isError: true,
        isFetchNextPageError: false,
      }),
    ).toBe('initial')
  })
})
