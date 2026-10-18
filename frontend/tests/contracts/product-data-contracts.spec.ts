import { describe, expect, it } from 'vitest'
import {
  mapProductDataRow,
  productDataParams,
  type ProductDataRowDto,
} from '../../src/features/product-data/api/product-data-real'
import { PRIMARY_PRODUCT_METRICS } from '../../src/features/product-data/model/metrics'
import {
  emptyProductFilters,
  formatProductMetric,
  productPeriod,
} from '../../src/features/product-data/model/query'
import type { ProductDataQuery } from '../../src/features/product-data/model/types'

const EXPECTED_METRICS = [
  ['exposureCount', 'product_show_cnt', 5, 'count'],
  ['clickCount', 'product_click_cnt', 5, 'count'],
  ['exposureClickRate', 'product_show_click_converse_uv_rate', 4, 'ratio'],
  ['cartUsers', 'click_add_to_cart_uv', 5, 'count'],
  ['visitCartRate', 'product_add_show_converse_uv_ratio', 4, 'ratio'],
  ['netOrders', 'net_pay_cnt', 5, 'count'],
  ['refundRelatedOrders', 'pay_cnt_exclude_refund', 5, 'count'],
  ['clickPayRate', 'product_click_pay_converse_uv_rate', 4, 'ratio'],
  ['payTimeRefundRate', 'pay_refund_ratio', 4, 'ratio'],
  ['pay_amt', 'pay_amt', 3, 'amount'],
  ['pay_cnt', 'pay_cnt', 5, 'count'],
  ['pay_ucnt', 'pay_ucnt', 5, 'count'],
  ['payPerOrder', 'per_user_price', 3, 'amount'],
  ['payTimeRefundAmount', 'pay_refund_success_amt', 3, 'amount'],
  ['payTimeRefundOrders', 'pay_refund_success_order_cnt', 5, 'count'],
  ['product_show_ucnt', 'product_show_ucnt', 5, 'count'],
  ['product_click_ucnt', 'product_click_ucnt', 5, 'count'],
] as const

function dto(): ProductDataRowDto {
  return {
    shop_product_id: '00000000-0000-0000-0000-000000000101',
    generation_id: '00000000-0000-0000-0000-000000000102',
    shop_id: '00000000-0000-0000-0000-000000000103',
    shop_name: 'Synthetic shop',
    product_id: '9000000000000000001',
    title: 'Synthetic product',
    image_url: 'https://example.test/product.png',
    metrics: Object.fromEntries(
      EXPECTED_METRICS.map(([, code, rawUnit]) => [
        code,
        {
          state: 'available' as const,
          raw_value: '0',
          raw_unit: rawUnit,
          unit_verified: true,
        },
      ]),
    ),
    scope: {
      shop_id: '00000000-0000-0000-0000-000000000103',
      period: '1d',
      start_date: '2026-10-17',
      end_date: '2026-10-17',
      timezone: 'Asia/Shanghai',
      platform: 'douyin',
      sale_type: '1',
      content_type: '1',
      request_contract: 'compass_product_list_request74_v1',
      metric_contract: 'compass_product_list_core17_v1',
    },
    retrieved_at: '2026-10-18T00:00:00+08:00',
  }
}

function query(preset: 'yesterday' | 'last7Days' | 'last30Days') {
  const filters = { ...emptyProductFilters(), datePreset: preset }
  return {
    filters,
    period: productPeriod(filters, new Date('2026-10-17T16:30:00.000Z')),
    page: 1,
    pageSize: 20,
    sort: null,
  } satisfies ProductDataQuery
}

describe('Product Data critical contract registry', () => {
  it('keeps the exact 17 frontend consumers, platform codes, units and kinds', () => {
    const actual = PRIMARY_PRODUCT_METRICS.map((metric) => [
      metric.id,
      metric.platformCode,
      metric.rawUnitCode,
      metric.format,
    ])
    expect(actual).toEqual(EXPECTED_METRICS)

    const mutated = actual.map((metric) => [...metric])
    mutated[0]![2] = 4
    expect(mutated).not.toEqual(EXPECTED_METRICS)
  })

  it('keeps zero distinct from missing, null and invalid observations', () => {
    const raw = dto()
    raw.metrics.product_show_cnt = {
      state: 'missing',
      raw_value: null,
      raw_unit: null,
      unit_verified: false,
    }
    raw.metrics.product_click_cnt = {
      state: 'null',
      raw_value: null,
      raw_unit: 5,
      unit_verified: true,
    }
    raw.metrics.net_pay_cnt = {
      state: 'invalid',
      raw_value: null,
      raw_unit: null,
      unit_verified: false,
    }

    const mapped = mapProductDataRow(raw)
    expect(mapped.metrics.pay_cnt).toMatchObject({
      state: 'available',
      value: '0',
      unit: 'count',
    })
    expect(formatProductMetric(mapped.metrics.pay_cnt)).toBe('0')
    expect(mapped.metrics.exposureCount.state).toBe('missing')
    expect(mapped.metrics.clickCount.state).toBe('null')
    expect(mapped.metrics.netOrders.state).toBe('invalid')
  })

  it('preserves exact amount, ratio and large count scaling', () => {
    const raw = dto()
    raw.metrics.pay_amt!.raw_value = '12345678901234567890.1234567890123456789'
    raw.metrics.pay_refund_ratio!.raw_value = '0.12345678901234567890123456789'
    raw.metrics.pay_cnt!.raw_value = '900719925474099312345'

    const mapped = mapProductDataRow(raw)
    expect(mapped.metrics.pay_amt.value).toBe(
      '123456789012345678.901234567890123456789',
    )
    expect(mapped.metrics.payTimeRefundRate.value).toBe(
      '0.12345678901234567890123456789',
    )
    expect(mapped.metrics.pay_cnt.value).toBe('900719925474099312345')
    expect(formatProductMetric(mapped.metrics.payTimeRefundRate)).toBe('12.35%')
  })

  it('freezes 1/7/30-day Shanghai windows and current request defaults', () => {
    const one = query('yesterday')
    const seven = query('last7Days')
    const thirty = query('last30Days')

    expect(one.period).toEqual({
      startDate: '2026-10-17',
      endDate: '2026-10-17',
    })
    expect(seven.period).toEqual({
      startDate: '2026-10-11',
      endDate: '2026-10-17',
    })
    expect(thirty.period).toEqual({
      startDate: '2026-09-18',
      endDate: '2026-10-17',
    })
    expect(productDataParams(one)).toMatchObject({
      period: '1d',
      start_date: '2026-10-17',
      end_date: '2026-10-17',
      sale_type: '1',
      content_type: '1',
      page: 1,
      page_size: 20,
    })
    expect(productDataParams(seven).period).toBe('7d')
    expect(productDataParams(thirty).period).toBe('30d')
  })
})
