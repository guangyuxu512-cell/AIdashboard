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
    })
    expect(result.tablePage).toEqual({ total: 1, page: 1, pageSize: 10 })
    expect(result.collectionAvailable).toBe(true)
    expect(result.summary.turnoverComparison).toEqual({
      state: 'increase',
      percentage: 12.5,
      favorable: true,
    })
  })

  it('submits the selected real date and scope as an asynchronous collection request', async () => {
    const post = vi.spyOn(httpClient, 'post').mockResolvedValue({
      data: {
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
    })

    await operatingDashboardApi.enqueueCollection({
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
  })
})
