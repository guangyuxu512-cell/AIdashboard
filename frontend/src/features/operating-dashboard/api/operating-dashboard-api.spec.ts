import { afterEach, describe, expect, it, vi } from 'vitest'

import { httpClient } from '@/shared/api'

import { operatingDashboardApi } from './operating-dashboard-api'

const filters = {
  datePreset: 'yesterday' as const,
  customDateRange: null,
  platform: 'douyin' as const,
  shopId: 'shop-1',
}

const dashboardDto = {
  date_range: { start_date: '2026-09-20', end_date: '2026-09-20' },
  comparison_date_range: { start_date: '2026-09-19', end_date: '2026-09-19' },
  trend_date_range: { start_date: '2026-09-14', end_date: '2026-09-20' },
  all_available_shops: [
    { shop_id: 'shop-1', shop_name: '测试店铺', platform: 'douyin' },
  ],
  summary: {
    turnover_cents: 98660,
    order_count: 93,
    refund_order_count: 9,
    refund_order_coverage_complete: true,
    shop_count: 1,
    turnover_comparison: {
      state: 'increase',
      percentage: 12.5,
      favorable: true,
    },
    order_comparison: {
      state: 'unavailable',
      percentage: null,
      favorable: null,
    },
    refund_order_comparison: {
      state: 'unavailable',
      percentage: null,
      favorable: null,
    },
    shop_count_comparison: {
      state: 'unavailable',
      percentage: null,
      favorable: null,
    },
  },
  trend: [
    {
      business_date: '2026-09-20',
      turnover_cents: 98660,
      order_count: 93,
      coverage_complete: true,
    },
  ],
  table: {
    items: [
      {
        shop_id: 'shop-1',
        shop_name: '测试店铺',
        platform: 'douyin',
        turnover_cents: 98660,
        order_count: 93,
        refund_order_count: 9,
        refund_order_coverage_complete: true,
        experience_score: null,
        collected_at: '2026-09-21T00:05:00+08:00',
        coverage_complete: true,
        not_operating_for_range: false,
      },
    ],
    total: 1,
    page: 1,
    page_size: 10,
  },
  coverage: {
    state: 'available',
    supported_shop_count: 1,
    collected_shop_days: 1,
    total_shop_days: 1,
    missing_shop_days: 0,
    missing_samples: [
      {
        shop_id: 'shop-1',
        shop_name: '测试店铺',
        business_date: '2026-09-20',
        state: 'failed' as const,
        failure_reason: '抖店经营数据响应无效',
      },
    ],
    missing_samples_truncated: false,
    manual_backfill_required: false,
    not_operating_shop_days: 0,
    shops_with_unknown_operating_start: 0,
    no_operating_scope: false,
  },
  collection_available: true,
}

afterEach(() => vi.restoreAllMocks())

describe('operatingDashboardApi', () => {
  it('uses the formal Backend read contract and explicitly maps snake-case DTOs', async () => {
    const get = vi
      .spyOn(httpClient, 'get')
      .mockResolvedValue({ data: dashboardDto })

    const result = await operatingDashboardApi.read({
      range: { startDate: '2026-09-20', endDate: '2026-09-20' },
      filters,
      sort: { field: 'turnoverCents', direction: 'desc' },
      page: 1,
      pageSize: 10,
    })

    expect(get).toHaveBeenCalledWith('/api/v1/operating-dashboard', {
      params: {
        start_date: '2026-09-20',
        end_date: '2026-09-20',
        platform: 'douyin',
        shop_id: 'shop-1',
        sort_field: 'turnover_cents',
        sort_direction: 'desc',
        page: 1,
        page_size: 10,
      },
    })
    expect(result.tableRows[0]).toMatchObject({
      shopId: 'shop-1',
      turnoverCents: 98660,
      refundOrderCount: 9,
      refundOrderCoverageComplete: true,
      experience: null,
      coverageComplete: true,
      notOperatingForRange: false,
    })
    expect(result.trend[0]?.coverageComplete).toBe(true)
    expect(result.tablePage).toEqual({ total: 1, page: 1, pageSize: 10 })
    expect(result.coverage).toMatchObject({
      collectedShopDays: 1,
      totalShopDays: 1,
      missingShopDays: 0,
      noOperatingScope: false,
    })
    expect(result.coverage.missingSamples).toEqual([
      {
        shopId: 'shop-1',
        shopName: '测试店铺',
        businessDate: '2026-09-20',
        state: 'failed',
        failureReason: '抖店经营数据响应无效',
      },
    ])
    expect(result.collectionAvailable).toBe(true)
    expect(result.summary.turnoverComparison).toEqual({
      state: 'increase',
      percentage: 12.5,
      favorable: true,
    })
  })

})
