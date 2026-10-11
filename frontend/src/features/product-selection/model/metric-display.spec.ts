import { describe, expect, it } from 'vitest'
import { formatSelectionInterval } from './metric-display'
import { formatReviewRate } from './candidate-display'
import type { SelectionMetricDto } from '../api/selection-read-api'

function endpoints(
  a: string,
  b: string,
  unit: string | null,
): NonNullable<SelectionMetricDto['value_range']> {
  return [
    { value: a, value_type: 'int', unit },
    { value: b, value_type: 'int', unit },
  ]
}

describe('confirmed short-video display units', () => {
  it.each([
    ['100000', '250000', '10万–25万'],
    ['10000', '25000', '1万–2.5万'],
    ['250', '500', '250–500'],
    ['0', '0', '0–0'],
    ['100000000', '250000000', '1亿–2.5亿'],
  ])('formats both count endpoints %s/%s', (a, b, expected) => {
    expect(formatSelectionInterval(endpoints(a, b, 'number'), 'count')).toBe(
      expected,
    )
  })
  it('converts confirmed price/fen to yuan before compact formatting, without changing raw facts', () => {
    const raw = endpoints('50000000', '75000000', 'price')
    expect(formatSelectionInterval(raw, 'amount')).toBe('¥50万–75万')
    expect(raw[0].value).toBe('50000000')
    expect(
      formatSelectionInterval(endpoints('12345', '25000', 'price'), 'amount'),
    ).toBe('¥123.45–250')
    expect(
      formatSelectionInterval(
        endpoints('10000000000', '25000000000', 'price'),
        'amount',
      ),
    ).toBe('¥1亿–2.5亿')
    expect(
      formatSelectionInterval(endpoints('0', '0', 'price'), 'amount'),
    ).toBe('¥0–0')
  })
  it('does not invent currency/scaling for null or mixed unknown units', () => {
    expect(
      formatSelectionInterval(
        endpoints('50000000', '75000000', null),
        'amount',
      ),
    ).toBe('50000000–75000000')
    const mixed = endpoints('50000000', '75000000', 'price')
    mixed[1].unit = 'unknown'
    expect(formatSelectionInterval(mixed, 'amount')).toBe('50000000–75000000')
  })
  it('uses the existing percent formatter for ratio, zero and missing values', () => {
    expect(formatReviewRate(0.0006711409395973154)).toBe('0.07%')
    expect(formatReviewRate(0)).toBe('0.00%')
    expect(formatReviewRate(null)).toBe('—')
  })
})
