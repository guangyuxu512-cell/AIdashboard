import { describe, expect, it } from 'vitest'
import { PRIMARY_PRODUCT_METRICS } from '../model/metrics'
import { emptyProductFilters, formatProductMetric } from '../model/query'
import type { ProductDataQuery } from '../model/types'
import {
  mapProductDataRow,
  productDataParams,
  type ProductDataRowDto,
} from './product-data-real'

function row(): ProductDataRowDto {
  return {
    shop_product_id: 'synthetic-stable',
    generation_id: 'synthetic-generation',
    shop_id: 'synthetic-shop',
    shop_name: 'Synthetic shop',
    product_id: '900719925474099312345',
    title: null,
    image_url: null,
    retrieved_at: '2026-10-17T00:00:00Z',
    scope: {
      shop_id: 'synthetic-shop',
      period: '1d',
      start_date: '2026-10-16',
      end_date: '2026-10-16',
      timezone: 'Asia/Shanghai',
      platform: 'douyin',
      sale_type: '1',
      content_type: '1',
      request_contract: 'compass_product_list_request74_v1',
      metric_contract: 'compass_product_list_core17_v1',
    },
    metrics: Object.fromEntries(
      PRIMARY_PRODUCT_METRICS.map((metric) => [
        metric.platformCode,
        {
          state: 'available',
          raw_value: '0',
          raw_unit: metric.rawUnitCode,
          unit_verified: true,
        },
      ]),
    ),
  }
}
const metricCodes = [
  'pay_amt',
  'per_user_price',
  'pay_refund_success_amt',
  'product_show_click_converse_uv_rate',
  'product_add_show_converse_uv_ratio',
  'product_click_pay_converse_uv_rate',
  'pay_refund_ratio',
] as const
const metricIds = [
  'pay_amt',
  'payPerOrder',
  'payTimeRefundAmount',
  'exposureClickRate',
  'visitCartRate',
  'clickPayRate',
  'payTimeRefundRate',
] as const

describe('Verified official product-list cell units', () => {
  // Existing three successful windows, numeric whitelist only; not a Mock fixture.
  it.each([
    [
      '1d',
      [
        '88820',
        '1096',
        '4180',
        '0.016627735006703618',
        '0.0005943413177790986',
        '0.06733167082294264',
        '0.04706147264129701',
      ],
      ['¥888.20', '¥10.96', '¥41.80', '1.66%', '0.06%', '6.73%', '4.71%'],
    ],
    [
      '7d',
      [
        '404513',
        '1021',
        '30013',
        '0.01508607663100517',
        '0.0004725560336064268',
        '0.07211801129120379',
        '0.07419539050660919',
      ],
      ['¥4,045.13', '¥10.21', '¥300.13', '1.51%', '0.05%', '7.21%', '7.42%'],
    ],
    [
      '30d',
      [
        '1477108',
        '1014',
        '143938',
        '0.020178538889400067',
        '0.0007180525260835287',
        '0.06509008002145827',
        '0.0974458198046453',
      ],
      ['¥14,771.08', '¥10.14', '¥1,439.38', '2.02%', '0.07%', '6.51%', '9.74%'],
    ],
  ])(
    'formats all seven %s observations without modifying raw values',
    (_period, values, expected) => {
      const dto = row()
      metricCodes.forEach((code, index) => {
        dto.metrics[code]!.raw_value = values[index]!
      })
      const mapped = mapProductDataRow(dto)
      metricIds.forEach((id, index) => {
        expect(formatProductMetric(mapped.metrics[id])).toBe(expected[index])
        expect(mapped.metrics[id].rawValue).toBe(values[index])
        expect(mapped.metrics[id].rawUnit).toBe(index < 3 ? 3 : 4)
      })
      expect(dto.metrics.pay_amt!.raw_value).toBe(values[0])
    },
  )
  it.each([
    'exposureClickRate',
    'visitCartRate',
    'clickPayRate',
    'payTimeRefundRate',
  ] as const)(
    'sends %s percentage-point boundaries as exact raw fractions',
    (id) => {
      const query: ProductDataQuery = {
        filters: emptyProductFilters(),
        period: { startDate: '2026-10-16', endDate: '2026-10-16' },
        page: 1,
        pageSize: 20,
        sort: { field: id, direction: 'asc' },
      }
      query.filters.metricRanges[id] = {
        choice: 'custom',
        min: 0.29,
        max: 1.01,
      }
      const params = productDataParams(query)
      expect(JSON.parse(params.ranges)).toEqual([
        {
          metric: PRIMARY_PRODUCT_METRICS.find((metric) => metric.id === id)!
            .platformCode,
          min_value: '0.0029',
          max_value: '0.0101',
        },
      ])
    },
  )
  it('keeps unverified or wrong units hidden and preserves true money/rate zeros', () => {
    const dto = row()
    let mapped = mapProductDataRow(dto)
    expect(formatProductMetric(mapped.metrics.pay_amt)).toBe('¥0.00')
    expect(formatProductMetric(mapped.metrics.payTimeRefundRate)).toBe('0.00%')
    for (const code of metricCodes) dto.metrics[code]!.unit_verified = false
    mapped = mapProductDataRow(dto)
    for (const id of metricIds) {
      expect(mapped.metrics[id].state).toBe('unit_unverified')
      expect(formatProductMetric(mapped.metrics[id])).toBe('—')
    }
    dto.metrics.pay_amt!.unit_verified = true
    dto.metrics.pay_amt!.raw_unit = 6
    expect(formatProductMetric(mapProductDataRow(dto).metrics.pay_amt)).toBe(
      '—',
    )
    dto.metrics.pay_amt!.raw_unit = 3
    dto.metrics.pay_amt!.raw_value = '-1'
    expect(mapProductDataRow(dto).metrics.pay_amt).toMatchObject({
      state: 'invalid',
      rawValue: '-1',
      value: null,
    })
  })
  it.each([
    ['custom', null, 2, null, '0.02'],
    ['custom', 1, null, '0.01', null],
    ['preset-4', null, null, '0.5', null],
  ] as const)(
    'serializes a %s one-sided ratio range without rounding',
    (choice, min, max, expectedMin, expectedMax) => {
      const filters = emptyProductFilters()
      filters.metricRanges.payTimeRefundRate = { choice, min, max }
      const params = productDataParams({
        filters,
        period: { startDate: '2026-10-16', endDate: '2026-10-16' },
        page: 1,
        pageSize: 20,
        sort: null,
      })
      expect(JSON.parse(params.ranges)).toEqual([
        {
          metric: 'pay_refund_ratio',
          min_value: expectedMin,
          max_value: expectedMax,
        },
      ])
    },
  )
  it.each([-1, Infinity, NaN])(
    'rejects invalid percent boundary %s rather than dropping it',
    (min) => {
      const filters = emptyProductFilters()
      filters.metricRanges.clickPayRate = { choice: 'custom', min, max: null }
      expect(() =>
        productDataParams({
          filters,
          period: { startDate: '2026-10-16', endDate: '2026-10-16' },
          page: 1,
          pageSize: 20,
          sort: null,
        }),
      ).toThrow()
    },
  )
  it('does not map legacy amount or wrong ratio aliases into new query fields', () => {
    const filters = emptyProductFilters()
    expect(() =>
      productDataParams({
        filters,
        period: { startDate: '2026-10-16', endDate: '2026-10-16' },
        page: 1,
        pageSize: 20,
        sort: { field: 'refund_amt', direction: 'asc' },
      }),
    ).toThrow('基准切片')
  })
})
