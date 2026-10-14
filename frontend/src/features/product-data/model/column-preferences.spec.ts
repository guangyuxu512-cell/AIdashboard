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
  it('preserves column order per user and resets corrupt/unknown preferences', () => {
    saveProductColumns('user-a', ['receive_amt', 'shop', 'product_click_ucnt'])
    saveProductColumns('user-b', ['pay_cnt'])
    expect(readProductColumns('user-a')).toEqual([
      'receive_amt',
      'shop',
      'product_click_ucnt',
    ])
    expect(readProductColumns('user-b')).toEqual(['pay_cnt'])
    expect(readProductColumns(null)).toEqual(DEFAULT_PRODUCT_COLUMNS)
    expect(normalizeProductColumns(['shop', 'shop', 'unknown'])).toEqual([
      'shop',
    ])
    window.localStorage.setItem(
      'control-center.product-data.columns.v1.user-a',
      '{broken',
    )
    expect(readProductColumns('user-a')).toEqual(DEFAULT_PRODUCT_COLUMNS)
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
