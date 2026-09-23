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
    return_quantity: null,
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
    return_comparison: {
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
        return_quantity: null,
        experience_score: null,
        collected_at: '2026-09-21T00:05:00+08:00',
        coverage_complete: true,
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
    missing_samples: [],
    missing_samples_truncated: false,
    manual_backfill_required: false,
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
      returnQuantity: null,
      experience: null,
      coverageComplete: true,
    })
    expect(result.trend[0]?.coverageComplete).toBe(true)
    expect(result.tablePage).toEqual({ total: 1, page: 1, pageSize: 10 })
    expect(result.coverage).toMatchObject({
      collectedShopDays: 1,
      totalShopDays: 1,
      missingShopDays: 0,
    })
    expect(result.collectionAvailable).toBe(true)
    expect(result.summary.turnoverComparison).toEqual({
      state: 'increase',
      percentage: 12.5,
      favorable: true,
    })
  })

  it('submits the selected real date and scope for backend gap checking', async () => {
    const post = vi.spyOn(httpClient, 'post').mockResolvedValue({
      data: {
        state: 'collection_queued',
        message: '已按缺口检查采集进度',
        collection_job: {
          collection_job_id: 'job-1',
          status: 'pending',
          counts: {
            pending: 1,
            running: 0,
            succeeded: 0,
            failed: 0,
            skipped: 0,
            paused_reauthorization: 0,
          },
          items: [],
        },
        missing_shop_days: 1,
        queued_shop_days: 1,
        active_shop_days: 0,
        blocked_shop_days: 0,
      },
    })

    const result = await operatingDashboardApi.requestCollectionUpdate({
      range: { startDate: '2026-09-18', endDate: '2026-09-20' },
      filters,
    })

    expect(post).toHaveBeenCalledWith(
      '/api/v1/operating-dashboard/collections',
      {
        start_date: '2026-09-18',
        end_date: '2026-09-20',
        platform: 'douyin',
        shop_id: 'shop-1',
      },
    )
    expect(result.collectionJob?.collection_job_id).toBe('job-1')
  })

  it('uses the explicit scoped recollect endpoint only after user intent', async () => {
    const post = vi.spyOn(httpClient, 'post').mockResolvedValue({
      data: {
        state: 'up_to_date',
        message: '数据已是最新，无需重新采集',
        collection_job: null,
        missing_shop_days: 0,
        queued_shop_days: 0,
        active_shop_days: 0,
        blocked_shop_days: 0,
      },
    })

    const result = await operatingDashboardApi.requestCollectionUpdate({
      range: { startDate: '2026-09-18', endDate: '2026-09-20' },
      filters,
      forceRecollect: true,
    })

    expect(post).toHaveBeenCalledWith(
      '/api/v1/operating-dashboard/collections/recollect',
      {
        start_date: '2026-09-18',
        end_date: '2026-09-20',
        platform: 'douyin',
        shop_id: 'shop-1',
      },
    )
    expect(result).toMatchObject({
      state: 'up_to_date',
      collectionJob: null,
      queuedShopDays: 0,
    })
  })
})
