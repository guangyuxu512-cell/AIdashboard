import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  buildOperatingDashboardRead,
  buildOperatingDashboardUnavailableRead,
  formatShanghaiDate,
  getPreviousOperatingDashboardDateRange,
  resolveOperatingDashboardDateRange,
} from './dashboard'
import { createOperatingDashboardMockSource as createMockSource } from './mock-source'
import type { OperatingDashboardFilters, OperatingDashboardRecord } from './types'

const now = new Date('2026-09-21T04:00:00.000Z')
const yesterdayFilters: OperatingDashboardFilters = {
  datePreset: 'yesterday',
  customDateRange: null,
  platform: null,
  shopId: null,
}

afterEach(() => vi.useRealTimers())

describe('operating dashboard date and aggregation model', () => {
  it('uses Asia/Shanghai and never queries today by default', () => {
    expect(formatShanghaiDate(now)).toBe('2026-09-21')
    expect(resolveOperatingDashboardDateRange(yesterdayFilters, now)).toEqual({
      startDate: '2026-09-20',
      endDate: '2026-09-20',
    })
    expect(
      getPreviousOperatingDashboardDateRange({
        startDate: '2026-09-18',
        endDate: '2026-09-20',
      }),
    ).toEqual({ startDate: '2026-09-15', endDate: '2026-09-17' })
  })

  it('uses a seven-day trend for the yesterday shortcut', () => {
    const records: OperatingDashboardRecord[] = [
      {
        shopId: 'shop-a',
        shopName: '店铺 A',
        platform: 'douyin',
        businessDate: '2026-09-20',
        turnoverCents: 100,
        orderCount: 1,
        returnQuantity: 0,
        experience: null,
        collectedAt: '2026-09-20T08:00:00+08:00',
      },
    ]

    const result = buildOperatingDashboardRead(records, yesterdayFilters, now)

    expect(result.trendDateRange).toEqual({
      startDate: '2026-09-14',
      endDate: '2026-09-20',
    })
    expect(result.trend).toHaveLength(7)
    expect(result.trend[0]?.turnoverCents).toBeNull()
    expect(result.trend[6]?.turnoverCents).toBe(100)
  })

  it('keeps missing values missing and avoids percentage infinities', () => {
    const records: OperatingDashboardRecord[] = [
      {
        shopId: 'shop-a',
        shopName: '店铺 A',
        platform: 'douyin',
        businessDate: '2026-09-20',
        turnoverCents: 100,
        orderCount: null,
        returnQuantity: null,
        experience: null,
        collectedAt: '2026-09-20T08:00:00+08:00',
      },
      {
        shopId: 'shop-a',
        shopName: '店铺 A',
        platform: 'douyin',
        businessDate: '2026-09-19',
        turnoverCents: 0,
        orderCount: null,
        returnQuantity: null,
        experience: null,
        collectedAt: '2026-09-19T08:00:00+08:00',
      },
    ]

    const result = buildOperatingDashboardRead(records, yesterdayFilters, now)

    expect(result.summary.orderCount).toBeNull()
    expect(result.summary.returnQuantity).toBeNull()
    expect(result.summary.turnoverComparison).toEqual({
      state: 'unavailable',
    })
    expect(result.tableRows[0]?.orderCount).toBeNull()
  })

  it('applies platform and shop filtering before table rows are assembled', () => {
    const records = [
      {
        shopId: 'shop-a',
        shopName: '店铺 A',
        platform: 'douyin' as const,
        businessDate: '2026-09-20',
        turnoverCents: 100,
        orderCount: 1,
        returnQuantity: 0,
        experience: null,
        collectedAt: '2026-09-20T08:00:00+08:00',
      },
      {
        shopId: 'shop-b',
        shopName: '店铺 B',
        platform: 'pdd' as const,
        businessDate: '2026-09-20',
        turnoverCents: 200,
        orderCount: 2,
        returnQuantity: 1,
        experience: null,
        collectedAt: '2026-09-20T08:00:00+08:00',
      },
    ]

    const result = buildOperatingDashboardRead(
      records,
      { ...yesterdayFilters, platform: 'pdd' },
      now,
    )

    expect(result.tableRows.map((row) => row.shopId)).toEqual(['shop-b'])
    expect(result.summary.shopCount).toBe(1)
    expect(result.availableShops.map((shop) => shop.shopId)).toEqual(['shop-b'])
    expect(result.allAvailableShops.map((shop) => shop.shopId)).toEqual([
      'shop-a',
      'shop-b',
    ])
  })

  it('keeps authorized shop identity visible without inventing operating data', () => {
    const shops = [
      { shopId: 'shop-a', shopName: '店铺 A', platform: 'douyin' as const },
      { shopId: 'shop-b', shopName: '店铺 B', platform: 'pdd' as const },
    ]

    const result = buildOperatingDashboardUnavailableRead(
      yesterdayFilters,
      shops,
      [shops[0]!],
      2,
      now,
    )

    expect(result.summary).toMatchObject({
      turnoverCents: null,
      orderCount: null,
      returnQuantity: null,
      shopCount: 2,
    })
    expect(result.trend).toHaveLength(7)
    expect(result.trend.every((point) => point.turnoverCents === null)).toBe(true)
    expect(result.tableRows).toEqual([
      expect.objectContaining({
        shopId: 'shop-a',
        shopName: '店铺 A',
        platform: 'douyin',
        turnoverCents: null,
        orderCount: null,
        returnQuantity: null,
        experience: null,
        collectedAt: null,
      }),
    ])
  })

  it('keeps a successful empty shop scope distinct from an unavailable scope', () => {
    const result = buildOperatingDashboardUnavailableRead(
      yesterdayFilters,
      [],
      [],
      0,
      now,
    )

    expect(result.summary.shopCount).toBe(0)
    expect(result.tableRows).toEqual([])
    expect(result.summary.turnoverCents).toBeNull()
  })
})

describe('operating dashboard Mock refresh', () => {
  it('reports a partial failure once and permits the same scope to recover', async () => {
    vi.useFakeTimers()
    const source = createMockSource(now)
    const first = source.refresh(yesterdayFilters)
    await vi.advanceTimersByTimeAsync(320)
    await expect(first).resolves.toMatchObject({
      status: 'partial_failure',
      attemptedShopCount: 11,
      refreshedShopCount: 10,
      failedShopNames: ['示例店铺 C'],
    })

    const second = source.refresh(yesterdayFilters)
    await vi.advanceTimersByTimeAsync(320)
    await expect(second).resolves.toMatchObject({
      status: 'completed',
      attemptedShopCount: 11,
      refreshedShopCount: 11,
      failedShopNames: [],
    })
  })
})
