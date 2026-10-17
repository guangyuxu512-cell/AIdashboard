import { beforeEach, describe, expect, it, vi } from 'vitest'
import { httpClient } from '@/shared/api'
import { PRIMARY_PRODUCT_METRICS } from '../model/metrics'
import { emptyProductFilters, formatProductMetric } from '../model/query'
import type { ProductDataQuery } from '../model/types'
import {
  createRealProductDataSource,
  mapProductDataRow,
  productDataParams,
  type ProductDataRowDto,
} from './product-data-real'

vi.mock('@/shared/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/shared/api')>()),
  httpClient: { get: vi.fn(), post: vi.fn() },
}))
const get = vi.mocked(httpClient.get)
const post = vi.mocked(httpClient.post)
function query(): ProductDataQuery {
  return {
    filters: emptyProductFilters(),
    period: { startDate: '2026-01-01', endDate: '2026-01-01' },
    page: 1,
    pageSize: 20,
    sort: null,
  }
}
function row(): ProductDataRowDto {
  return {
    shop_product_id: 'synthetic-stable-id',
    generation_id: 'synthetic-generation',
    shop_id: 'synthetic-shop',
    shop_name: 'Synthetic shop',
    product_id: '900719925474099312345',
    title: null,
    image_url: null,
    retrieved_at: '2026-01-02T02:00:00Z',
    scope: {
      shop_id: 'synthetic-shop',
      period: '1d',
      start_date: '2026-01-01',
      end_date: '2026-01-01',
      timezone: 'Asia/Shanghai',
      platform: 'douyin',
      sale_type: '1',
      content_type: '1',
      request_contract: 'compass_product_list_request74_v1',
      metric_contract: 'compass_product_list_core17_v1',
    },
    metrics: Object.fromEntries(
      PRIMARY_PRODUCT_METRICS.map((definition) => [
        definition.platformCode,
        {
          state: 'available',
          raw_value:
            definition.format === 'count'
              ? '900719925474099312345'
              : '0.103846080868261780123456789',
          raw_unit: definition.rawUnitCode,
          unit_verified: true,
        },
      ]),
    ),
  }
}
beforeEach(() => {
  get.mockReset()
  post.mockReset()
})
describe('Product Data typed Real adapter', () => {
  it('preserves exact identities and raw metadata while applying verified product-list units', () => {
    const mapped = mapProductDataRow(row())
    expect(mapped.productId).toBe('900719925474099312345')
    expect(formatProductMetric(mapped.metrics.pay_cnt)).toBe(
      '900,719,925,474,099,312,345',
    )
    expect(mapped.metrics.payTimeRefundRate).toMatchObject({
      state: 'available',
      value: '0.103846080868261780123456789',
      unit: 'ratio',
      rawUnit: 4,
      rawValue: '0.103846080868261780123456789',
    })
    expect(formatProductMetric(mapped.metrics.payTimeRefundRate)).toBe('10.38%')
    expect(mapped.metrics.pay_amt.state).toBe('available')
    expect(mapped.metrics.pay_amt.value).toBe('0.00103846080868261780123456789')
    expect(mapped.metrics.receive_amt.state).toBe('missing')
    expect(mapped.selling).toBeNull()
    expect(mapped.carrier).toBeNull()
    expect(mapped.groupingAvailable).toBe(false)
  })
  it('retains zero, missing, null, invalid and unit6 without substituting zeros', () => {
    const dto = row()
    dto.metrics.pay_cnt = {
      state: 'available',
      raw_value: '0',
      raw_unit: 5,
      unit_verified: true,
    }
    dto.metrics.product_show_cnt = {
      state: 'missing',
      raw_value: null,
      raw_unit: null,
      unit_verified: false,
    }
    dto.metrics.product_click_cnt = {
      state: 'null',
      raw_value: null,
      raw_unit: 5,
      unit_verified: true,
    }
    dto.metrics.net_pay_cnt = {
      state: 'invalid',
      raw_value: '-1',
      raw_unit: 5,
      unit_verified: true,
    }
    dto.metrics.pay_refund_ratio = {
      state: 'missing',
      raw_value: null,
      raw_unit: 6,
      unit_verified: false,
    }
    const mapped = mapProductDataRow(dto)
    expect(formatProductMetric(mapped.metrics.pay_cnt)).toBe('0')
    for (const id of [
      'exposureCount',
      'clickCount',
      'netOrders',
      'payTimeRefundRate',
    ] as const)
      expect(formatProductMetric(mapped.metrics[id])).toBe('—')
    expect(mapped.metrics.netOrders.rawValue).toBe('-1')
    expect(mapped.metrics.payTimeRefundRate.rawUnit).toBe(6)
  })
  it('sends only declared SQL-query fields, exact count ranges and paired sorting', async () => {
    const params = query()
    params.filters.metricRanges.exposureCount = {
      choice: 'custom',
      min: 0,
      max: 1000,
    }
    params.sort = { field: 'pay_cnt', direction: 'desc' }
    get.mockResolvedValue({
      data: {
        items: [row()],
        total: 29,
        page: 1,
        page_size: 20,
        coverage: {
          supported_shop_count: 2,
          collected_shop_count: 1,
          missing_shop_ids: ['missing-shop'],
          collection_available: false,
          unit_unconfirmed_codes: ['pay_amt'],
        },
      },
    })
    const page = await createRealProductDataSource().list(params)
    expect(get).toHaveBeenCalledExactlyOnceWith('/api/v1/product-data', {
      params: expect.objectContaining({
        period: '1d',
        sale_type: '1',
        content_type: '1',
        page: 1,
        page_size: 20,
        sort_field: 'pay_cnt',
        sort_direction: 'desc',
        ranges:
          '[{"metric":"product_show_cnt","min_value":"0","max_value":"1000"}]',
      }),
    })
    expect(page.total).toBe(29)
    expect(page.items).toHaveLength(1) // no local filtering or total recomputation
    expect(page.coverage).toMatchObject({
      collectionAvailable: false,
      collectedShopCount: 1,
      supportedShopCount: 2,
    })
  })
  it.each(['groupId', 'selling', 'carrier'] as const)(
    'does not silently drop unsupported %s',
    (field) => {
      const params = query()
      Object.assign(params.filters, {
        [field]:
          field === 'groupId' ? 'group' : field === 'selling' ? 'self' : 'live',
      })
      expect(() => productDataParams(params)).toThrow('基准切片')
    },
  )
  it('keeps unsupported dates blocked while allowing verified percent ranges and amount sort', () => {
    const params = query()
    params.filters.datePreset = 'custom'
    expect(() => productDataParams(params)).toThrow('基准切片')
    params.filters.datePreset = 'yesterday'
    params.filters.metricRanges.payTimeRefundRate = {
      choice: 'preset-0',
      min: null,
      max: null,
    }
    expect(JSON.parse(productDataParams(params).ranges)).toEqual([
      { metric: 'pay_refund_ratio', min_value: '0', max_value: '0.1' },
    ])
    params.filters = emptyProductFilters()
    params.sort = { field: 'pay_amt', direction: 'asc' }
    expect(productDataParams(params).sort_field).toBe('pay_amt')
    expect(get).not.toHaveBeenCalled()
  })
  it('propagates HTTP rejection without Mock fallback or invented groups', async () => {
    const error = new Error('synthetic real 403')
    get.mockRejectedValue(error)
    const source = createRealProductDataSource()
    await expect(source.list(query())).rejects.toBe(error)
    await expect(source.groups('shop')).rejects.toThrow('分组尚未接入')
    expect(get).toHaveBeenCalledTimes(1)
  })
  it('maps explicit manual submission and exact receipt lookup without inventing unknown totals', async () => {
    const data = {
      generation_id: 'synthetic-generation',
      scope: row().scope,
      status: 'running',
      stage: 'session_preparation',
      received_pages: 0,
      expected_total: null,
      received_total: null,
      pages_complete: false,
      raw_complete_rows: null,
      unit_complete_rows: null,
      failure_code: null,
      created_at: '2026-01-02T00:00:00Z',
      started_at: '2026-01-02T00:00:00Z',
      finished_at: null,
      published_at: null,
      lease_expired: false,
    }
    post.mockResolvedValue({ data })
    get.mockResolvedValue({ data })
    const source = createRealProductDataSource()
    const submitted = await source.collect!({
      shopId: 'synthetic-shop',
      period: '1d',
      submissionKey: 'synthetic-fixed-key',
    })
    expect(post).toHaveBeenCalledExactlyOnceWith(
      '/api/v1/product-data/collections',
      {
        shop_id: 'synthetic-shop',
        period: '1d',
        submission_key: 'synthetic-fixed-key',
        sale_type: '1',
        content_type: '1',
      },
    )
    expect(submitted).toMatchObject({
      id: 'synthetic-generation',
      expectedTotal: null,
      receivedTotal: null,
      rawCompleteRows: null,
    })
    expect(await source.collection!('synthetic-generation')).toEqual(submitted)
    expect(get).toHaveBeenCalledExactlyOnceWith(
      '/api/v1/product-data/collections/synthetic-generation',
    )
    expect(post).toHaveBeenCalledTimes(1)
  })
})
