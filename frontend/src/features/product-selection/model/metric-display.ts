import type { SelectionMetricDto } from '../api/selection-read-api'

function compact(value: number): string {
  const factor = value >= 100000000 ? 100000000 : value >= 10000 ? 10000 : 1
  const suffix = factor === 100000000 ? '亿' : factor === 10000 ? '万' : ''
  return `${Number((value / factor).toFixed(2))}${suffix}`
}

/** Display only: database decimals stay intact; ranges never become midpoints. */
export function formatSelectionInterval(
  endpoints: NonNullable<SelectionMetricDto['value_range']>,
  kind: 'count' | 'amount',
): string | null {
  if (endpoints.length !== 2) return null
  // Confirmed short-video price = fen; number = count. Unknown units keep raw
  // endpoints and have no invented currency/suffix/conversion.
  const unit = kind === 'amount' ? 'price' : 'number'
  const values = endpoints.map((entry) => Number(entry.value))
  if (
    endpoints.some(
      (entry) => entry.unit !== unit || entry.value.trim() === '',
    ) ||
    values.some((value) => !Number.isFinite(value) || value < 0)
  )
    return endpoints.map((entry) => entry.value).join('–')
  const factor = kind === 'amount' ? 100 : 1
  return `${kind === 'amount' ? '¥' : ''}${values.map((value) => compact(value / factor)).join('–')}`
}
