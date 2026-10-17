import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  normalizeProductColumns,
  readProductColumns,
  saveProductColumns,
} from './column-preferences'
import { DEFAULT_PRODUCT_COLUMNS } from './types'
import { formatProductMetric } from './query'

beforeEach(() => {
  window.localStorage.clear()
  vi.restoreAllMocks()
})
describe('product data personal fields', () => {
  it('migrates both historical ratio column IDs only at the preference boundary and preserves saved order', () => {
    const key = 'control-center.product-data.columns.v1.ratio-compat'
    const raw = JSON.stringify([
      'product_click_pay_ucnt_ratio',
      'shop',
      'product_click_show_ucnt_ratio',
      'clickPayRate',
      'exposureClickRate',
    ])
    window.localStorage.setItem(key, raw)
    const write = vi.spyOn(Storage.prototype, 'setItem')
    expect(readProductColumns('ratio-compat')).toEqual([
      'clickPayRate',
      'shop',
      'exposureClickRate',
    ])
    expect(write).not.toHaveBeenCalled()
    expect(window.localStorage.getItem(key)).toBe(raw)
  })
  it('migrates only the replaced refund-rate column preference, preserving order without reading old metric data or rewriting storage', () => {
    const key = 'control-center.product-data.columns.v1.refund-rate'
    const raw = JSON.stringify([
      'shop',
      'shippedReturnRate',
      'pay_amt',
      'payTimeRefundRate',
    ])
    window.localStorage.setItem(key, raw)
    const write = vi.spyOn(Storage.prototype, 'setItem')
    expect(readProductColumns('refund-rate')).toEqual([
      'shop',
      'payTimeRefundRate',
      'pay_amt',
    ])
    expect(write).not.toHaveBeenCalled()
    expect(window.localStorage.getItem(key)).toBe(raw)
  })
  it('keeps approved legacy choices, filters retired display keys and does not rewrite storage on read', () => {
    const key = 'control-center.product-data.columns.v1.legacy'
    const raw = JSON.stringify([
      'receive_amt',
      '曝光点击率',
      'shop',
      'product_click_show_ucnt_ratio',
      'refund_amt',
      '点击成交率',
      '转化率',
      'stock_cnt',
    ])
    window.localStorage.setItem(key, raw)
    const write = vi.spyOn(Storage.prototype, 'setItem')
    const expected = ['exposureClickRate', 'shop', 'clickPayRate'] as const
    expect(readProductColumns('legacy')).toEqual(expected)
    expect(write).not.toHaveBeenCalled()
    expect(window.localStorage.getItem(key)).toBe(raw)
    saveProductColumns('legacy', [...expected])
    expect(JSON.parse(window.localStorage.getItem(key)!)).toEqual(expected)
  })
  it('preserves each user selection and order while resetting corrupt or wholly retired preferences', () => {
    saveProductColumns('user-a', ['product_click_ucnt', 'shop', 'pay_amt'])
    saveProductColumns('user-b', ['pay_cnt'])
    expect(readProductColumns('user-a')).toEqual([
      'product_click_ucnt',
      'shop',
      'pay_amt',
    ])
    expect(readProductColumns('user-b')).toEqual(['pay_cnt'])
    expect(readProductColumns(null)).toEqual(DEFAULT_PRODUCT_COLUMNS)
    expect(normalizeProductColumns(['shop', 'shop', 'unknown'])).toEqual([
      'shop',
    ])
    expect(normalizeProductColumns(['receive_amt', 'stock_cnt'])).toEqual(
      DEFAULT_PRODUCT_COLUMNS,
    )
    window.localStorage.setItem(
      'control-center.product-data.columns.v1.user-a',
      '{broken',
    )
    expect(readProductColumns('user-a')).toEqual(DEFAULT_PRODUCT_COLUMNS)
  })
  it('stores traffic aliases as view preferences while reusing their canonical metrics', () => {
    saveProductColumns('aliases', [
      'trafficClickPayRate',
      'trafficExposureClickRate',
      'shop',
    ])
    expect(readProductColumns('aliases')).toEqual([
      'trafficClickPayRate',
      'trafficExposureClickRate',
      'shop',
    ])
  })
  it('surfaces write failure rather than pretending preferences were saved', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('unavailable')
    })
    expect(() => saveProductColumns('user-a', ['pay_cnt'])).toThrow(
      'unavailable',
    )
    expect(() => saveProductColumns(null, ['pay_cnt'])).toThrow('登录')
    expect(() => saveProductColumns('user-a', [])).toThrow('至少')
  })
  it('formats confirmed zero distinctly from absent and invalid metrics', () => {
    expect(
      formatProductMetric({ state: 'available', value: '0', unit: 'count' }),
    ).toBe('0')
    expect(
      formatProductMetric({ state: 'available', value: '0', unit: 'yuan' }),
    ).toBe('¥0.00')
    for (const state of ['missing', 'null', 'invalid'] as const)
      expect(formatProductMetric({ state, value: null, unit: 'count' })).toBe(
        '—',
      )
  })
})
