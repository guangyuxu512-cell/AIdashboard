import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  buildOperatingDashboardRead,
  buildOperatingDashboardUnavailableRead,
  formatShanghaiDate,
  getPreviousOperatingDashboardDateRange,
  resolveOperatingDashboardDateRange,
  sortOperatingDashboardRows,
} from './dashboard'
import { createOperatingDashboardMockSource as createMockSource } from './mock-source'
import type {
  OperatingDashboardFilters,
  OperatingDashboardRecord,
  OperatingDashboardTableRow,
} from './types'

const now = new Date('2026-09-21T04:00:00.000Z')
const yesterdayFilters: OperatingDashboardFilters = {
  datePreset: 'yesterday',
  customDateRange: null,
  platform: null,
  shopId: null,
}

function tableRow(
  input: Pick<OperatingDashboardTableRow, 'shopId' | 'shopName'> &
    Partial<Omit<OperatingDashboardTableRow, 'shopId' | 'shopName'>>,
): OperatingDashboardTableRow {
  return {
    shopId: input.shopId,
    shopName: input.shopName,
    platform: input.platform ?? 'douyin',
    turnoverCents: input.turnoverCents === undefined ? 0 : input.turnoverCents,
    orderCount: input.orderCount === undefined ? 0 : input.orderCount,
    returnQuantity:
      input.returnQuantity === undefined ? 0 : input.returnQuantity,
    experience: input.experience === undefined ? null : input.experience,
    collectedAt:
      input.collectedAt === undefined
        ? '2026-09-20T08:00:00+08:00'
        : input.collectedAt,
  }
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

  it('keeps confirmed Mock facts visible while marking a partial range', () => {
    const records: OperatingDashboardRecord[] = [
      {
        shopId: 'shop-a',
        shopName: '部分覆盖店铺',
        platform: 'douyin',
        businessDate: '2026-09-19',
        turnoverCents: 100,
        orderCount: 1,
        returnQuantity: null,
        experience: null,
        collectedAt: '2026-09-19T08:00:00+08:00',
      },
      {
        shopId: 'shop-b',
        shopName: '完整覆盖店铺',
        platform: 'douyin',
        businessDate: '2026-09-19',
        turnoverCents: 200,
        orderCount: 2,
        returnQuantity: null,
        experience: null,
        collectedAt: '2026-09-19T08:00:00+08:00',
      },
      {
        shopId: 'shop-b',
        shopName: '完整覆盖店铺',
        platform: 'douyin',
        businessDate: '2026-09-20',
        turnoverCents: 0,
        orderCount: 0,
        returnQuantity: null,
        experience: null,
        collectedAt: '2026-09-20T08:00:00+08:00',
      },
    ]
    const result = buildOperatingDashboardRead(
      records,
      {
        ...yesterdayFilters,
        datePreset: 'custom',
        customDateRange: [
          Date.parse('2026-09-19T00:00:00+08:00'),
          Date.parse('2026-09-20T00:00:00+08:00'),
        ],
      },
      now,
    )

    expect(result.summary.turnoverCents).toBe(300)
    expect(result.summary.orderCount).toBe(3)
    expect(result.summary.turnoverComparison).toEqual({ state: 'unavailable' })
    expect(result.coverage).toMatchObject({
      collectedShopDays: 3,
      totalShopDays: 4,
      missingShopDays: 1,
    })
    expect(result.tableRows).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          shopId: 'shop-a',
          turnoverCents: 100,
          coverageComplete: false,
        }),
        expect.objectContaining({
          shopId: 'shop-b',
          turnoverCents: 200,
          coverageComplete: true,
        }),
      ]),
    )
    expect(result.trend).toEqual([
      expect.objectContaining({
        businessDate: '2026-09-19',
        turnoverCents: 300,
        coverageComplete: true,
      }),
      expect.objectContaining({
        businessDate: '2026-09-20',
        turnoverCents: 0,
        coverageComplete: false,
      }),
    ])
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
    expect(result.trend.every((point) => point.turnoverCents === null)).toBe(
      true,
    )
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

describe('operating dashboard table ordering', () => {
  const rows = [
    tableRow({ shopId: 'shop-01', shopName: '阿店', turnoverCents: 12 }),
    tableRow({ shopId: 'shop-02', shopName: 'Beta', turnoverCents: 20 }),
    tableRow({ shopId: 'shop-tie-b', shopName: '同名店', turnoverCents: 20 }),
    tableRow({ shopId: 'shop-tie-a', shopName: '同名店', turnoverCents: 20 }),
    tableRow({ shopId: 'shop-zero', shopName: '零值店', turnoverCents: 0 }),
    tableRow({ shopId: 'shop-null', shopName: '缺失店', turnoverCents: null }),
    tableRow({ shopId: 'shop-07', shopName: '店铺 07', turnoverCents: 7 }),
    tableRow({ shopId: 'shop-08', shopName: '店铺 08', turnoverCents: 8 }),
    tableRow({ shopId: 'shop-09', shopName: '店铺 09', turnoverCents: 9 }),
    tableRow({ shopId: 'shop-10', shopName: '店铺 10', turnoverCents: 10 }),
    tableRow({ shopId: 'shop-11', shopName: '店铺 11', turnoverCents: 11 }),
    tableRow({ shopId: 'shop-max', shopName: '最大值店', turnoverCents: 999 }),
  ]

  it('sorts the complete filtered Mock result before pagination', () => {
    const descending = sortOperatingDashboardRows(rows, {
      field: 'turnoverCents',
      direction: 'desc',
    })

    expect(rows.slice(10).map((row) => row.shopId)).toContain('shop-max')
    expect(descending[0]?.shopId).toBe('shop-max')
    expect(descending.slice(0, 10).map((row) => row.shopId)).toContain(
      'shop-max',
    )
    expect(descending[descending.length - 1]?.shopId).toBe('shop-null')
    expect(descending.map((row) => row.shopId)).toEqual([
      'shop-max',
      'shop-02',
      'shop-tie-a',
      'shop-tie-b',
      'shop-01',
      'shop-11',
      'shop-10',
      'shop-09',
      'shop-08',
      'shop-07',
      'shop-zero',
      'shop-null',
    ])
  })

  it('keeps real zero sortable and missing values last in both directions', () => {
    const ascending = sortOperatingDashboardRows(rows, {
      field: 'turnoverCents',
      direction: 'asc',
    })
    const descending = sortOperatingDashboardRows(rows, {
      field: 'turnoverCents',
      direction: 'desc',
    })

    expect(ascending[0]?.shopId).toBe('shop-zero')
    expect(ascending[ascending.length - 1]?.shopId).toBe('shop-null')
    expect(descending[descending.length - 1]?.shopId).toBe('shop-null')
    expect(
      ascending.findIndex((row) => row.shopId === 'shop-zero'),
    ).toBeLessThan(ascending.findIndex((row) => row.shopId === 'shop-null'))
  })

  it('applies the same raw-value rule to order and return counts', () => {
    const countRows = [
      tableRow({
        shopId: 'shop-max',
        shopName: '最大值店',
        orderCount: 9,
        returnQuantity: 9,
      }),
      tableRow({
        shopId: 'shop-zero',
        shopName: '零值店',
        orderCount: 0,
        returnQuantity: 0,
      }),
      tableRow({
        shopId: 'shop-null',
        shopName: '缺失店',
        orderCount: null,
        returnQuantity: null,
      }),
    ]

    for (const field of ['orderCount', 'returnQuantity'] as const) {
      const ascending = sortOperatingDashboardRows(countRows, {
        field,
        direction: 'asc',
      })
      const descending = sortOperatingDashboardRows(countRows, {
        field,
        direction: 'desc',
      })
      expect(ascending.map((row) => row.shopId)).toEqual([
        'shop-zero',
        'shop-max',
        'shop-null',
      ])
      expect(descending.map((row) => row.shopId)).toEqual([
        'shop-max',
        'shop-zero',
        'shop-null',
      ])
    }
  })

  it('uses raw timestamps and a stable shop_id tie-breaker', () => {
    const timeRows = [
      tableRow({
        shopId: 'shop-later',
        shopName: '同名店',
        collectedAt: '2026-09-20T18:00:00+08:00',
      }),
      tableRow({
        shopId: 'shop-earlier',
        shopName: '同名店',
        collectedAt: '2026-09-20T08:00:00+08:00',
      }),
      tableRow({
        shopId: 'shop-time-null',
        shopName: '同名店',
        collectedAt: null,
      }),
      tableRow({
        shopId: 'shop-name-b',
        shopName: '同名店',
        collectedAt: '2026-09-20T12:00:00+08:00',
      }),
      tableRow({
        shopId: 'shop-name-a',
        shopName: '同名店',
        collectedAt: '2026-09-20T12:00:00+08:00',
      }),
    ]

    expect(
      sortOperatingDashboardRows(timeRows, {
        field: 'collectedAt',
        direction: 'asc',
      }).map((row) => row.shopId),
    ).toEqual([
      'shop-earlier',
      'shop-name-a',
      'shop-name-b',
      'shop-later',
      'shop-time-null',
    ])
    expect(
      sortOperatingDashboardRows(timeRows, {
        field: 'shopName',
        direction: 'asc',
      }).map((row) => row.shopId),
    ).toEqual([
      'shop-earlier',
      'shop-later',
      'shop-name-a',
      'shop-name-b',
      'shop-time-null',
    ])
    expect(sortOperatingDashboardRows(timeRows, null)).toEqual(
      sortOperatingDashboardRows(timeRows, {
        field: 'shopName',
        direction: 'asc',
      }),
    )
  })
})
