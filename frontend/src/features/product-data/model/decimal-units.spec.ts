import { describe, expect, it } from 'vitest'
import { formatProductDecimal, shiftProductDecimal } from './decimal-units'
import { formatProductMetric } from './query'

describe('Product-list exact decimal units', () => {
  it.each([
    ['88820', -2, '888.2'],
    ['0.01005', 2, '1.005'],
    ['900719925474099312345.005', -2, '9007199254740993123.45005'],
    ['0.29', -2, '0.0029'],
    ['1e-7', -2, '0.000000001'],
    ['1.01e2', -2, '1.01'],
    ['-0.000', 0, '0'],
    ['0.0000', 2, '0'],
  ] as const)(
    'shifts %s by %s decimal places exactly',
    (value, shift, expected) => {
      expect(shiftProductDecimal(value, shift)).toBe(expected)
    },
  )
  it.each(['', '-1', '-0.1', 'NaN', 'Infinity', '1,000', '0x11', '1e999999'])(
    'does not normalize invalid or negative %s',
    (value) => {
      expect(shiftProductDecimal(value, 0)).toBeNull()
    },
  )
  it.each([
    ['0.01005', 'ratio', '1.01%'],
    ['0', 'ratio', '0.00%'],
    ['1.2', 'ratio', '120.00%'],
    ['0', 'yuan', '¥0.00'],
    ['9007199254740993.005', 'yuan', '¥9,007,199,254,740,993.01'],
    ['0.9999999999999999999999999999999999', 'yuan', '¥1.00'],
  ] as const)(
    'rounds %s %s only at the final display',
    (value, unit, expected) => {
      expect(formatProductDecimal(value, unit)).toBe(expected)
    },
  )
  it('does not turn an unknown or invalid value into a genuine zero', () => {
    for (const state of [
      'missing',
      'null',
      'invalid',
      'unit_unverified',
    ] as const)
      expect(formatProductMetric({ state, value: '0', unit: 'yuan' })).toBe('—')
    expect(
      formatProductMetric({ state: 'available', value: '0', unit: null }),
    ).toBe('—')
    expect(
      formatProductMetric({ state: 'available', value: '-1', unit: 'yuan' }),
    ).toBe('—')
    expect(
      formatProductMetric({ state: 'available', value: '-0.00', unit: 'yuan' }),
    ).toBe('¥0.00')
  })
})
