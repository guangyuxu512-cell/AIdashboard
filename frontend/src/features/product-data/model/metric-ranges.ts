import { z } from 'zod'
import { productMetricDefinition } from './metrics'
import type { ProductMetric } from './types'

export const PRODUCT_RANGE_FILTERS = [
  {
    id: 'exposureCount',
    percent: false,
    boundaries: [0, 1000, 3000, 5000, 10000],
  },
  { id: 'clickCount', percent: false, boundaries: [0, 10, 50, 100, 200] },
  {
    id: 'product_click_show_ucnt_ratio',
    percent: true,
    boundaries: [0, 1, 2, 4, 6],
  },
  { id: 'cartUsers', percent: false, boundaries: [0, 10, 50, 100, 200] },
  { id: 'visitCartRate', percent: true, boundaries: [0, 5, 8, 10, 15] },
  {
    id: 'product_click_pay_ucnt_ratio',
    percent: true,
    boundaries: [0, 1, 2, 4, 6],
  },
  { id: 'netOrders', percent: false, boundaries: [0, 5, 10, 50, 200] },
  { id: 'refundRelatedOrders', percent: false, boundaries: [0, 5, 10, 20, 50] },
  { id: 'shippedReturnRate', percent: true, boundaries: [0, 10, 20, 30, 50] },
] as const
export type ProductRangeFilterId = (typeof PRODUCT_RANGE_FILTERS)[number]['id']
export type ProductRangeChoice =
  | 'unlimited'
  | 'custom'
  | 'preset-0'
  | 'preset-1'
  | 'preset-2'
  | 'preset-3'
  | 'preset-4'
export interface ProductRangeDraft {
  choice: ProductRangeChoice
  // UI units: count or percentage points, NOT raw platform units.
  min: number | null
  max: number | null
}
export type ProductRangeDrafts = Record<ProductRangeFilterId, ProductRangeDraft>
export type ProductRangeErrors = Partial<Record<ProductRangeFilterId, string>>
export interface ProductMetricInterval {
  metricId: ProductRangeFilterId
  min: number | null
  max: number | null
  minInclusive: true
  maxInclusive: false
  unit: 'count' | 'fraction'
}

const boundSchema = z
  .number()
  .finite('请输入有限数值')
  .nonnegative('不能输入负数')
  .nullable()
const customSchema = z
  .object({ min: boundSchema, max: boundSchema })
  .superRefine((value, ctx) => {
    if (value.min !== null && value.max !== null && value.min >= value.max)
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: '上限必须大于下限',
        path: ['max'],
      })
  })

export function emptyProductRangeDrafts(): ProductRangeDrafts {
  return Object.fromEntries(
    PRODUCT_RANGE_FILTERS.map(({ id }) => [
      id,
      { choice: 'unlimited', min: null, max: null },
    ]),
  ) as ProductRangeDrafts
}
export function productRangeLabel(id: ProductRangeFilterId): string {
  return productMetricDefinition(id)!.label
}
export function productRangeOptions(id: ProductRangeFilterId) {
  const definition = PRODUCT_RANGE_FILTERS.find((field) => field.id === id)!
  const suffix = definition.percent ? '%' : ''
  return [
    { label: '不限', value: 'unlimited' },
    ...definition.boundaries.map((min, index, bounds) => ({
      label:
        index === bounds.length - 1
          ? '≥ ' + min + suffix
          : min + suffix + '–<' + bounds[index + 1] + suffix,
      value: 'preset-' + index,
    })),
    { label: '自定义', value: 'custom' },
  ]
}
export function selectProductRange(
  choice: ProductRangeChoice | null,
  previous: ProductRangeDraft,
): ProductRangeDraft {
  const next = choice ?? 'unlimited'
  return {
    choice: next,
    min: next === 'custom' ? previous.min : null,
    max: next === 'custom' ? previous.max : null,
  }
}

export function compileProductRanges(drafts: ProductRangeDrafts): {
  intervals: ProductMetricInterval[]
  errors: ProductRangeErrors
} {
  const intervals: ProductMetricInterval[] = [],
    errors: ProductRangeErrors = {}
  for (const field of PRODUCT_RANGE_FILTERS) {
    const draft = drafts[field.id]
    if (draft.choice === 'unlimited') continue
    let min: number | null, max: number | null
    if (draft.choice === 'custom') {
      const parsed = customSchema.safeParse(draft)
      if (!parsed.success) {
        errors[field.id] = parsed.error.issues[0]!.message
        continue
      }
      ;({ min, max } = parsed.data)
      if (
        !field.percent &&
        [min, max].some((value) => value !== null && !Number.isInteger(value))
      ) {
        errors[field.id] = '数量边界须为非负整数'
        continue
      }
    } else {
      const index = Number(draft.choice.slice('preset-'.length))
      if (!/^preset-[0-4]$/.test(draft.choice)) {
        errors[field.id] = '请选择有效区间'
        continue
      }
      min = field.boundaries[index]!
      max = field.boundaries[index + 1] ?? null
    }
    if (min === null && max === null) continue
    const divisor = field.percent ? 100 : 1
    intervals.push({
      metricId: field.id,
      min: min === null ? null : min / divisor,
      max: max === null ? null : max / divisor,
      minInclusive: true,
      maxInclusive: false,
      unit: field.percent ? 'fraction' : 'count',
    })
  }
  return { intervals, errors }
}

export function matchesProductInterval(
  metric: ProductMetric,
  interval: ProductMetricInterval,
): boolean {
  if (
    metric.state !== 'available' ||
    metric.value === null ||
    metric.value.trim() === ''
  )
    return false
  const value = Number(metric.value)
  const expectedUnit = interval.unit === 'fraction' ? 'ratio' : 'count'
  return (
    Number.isFinite(value) &&
    value >= 0 &&
    metric.unit === expectedUnit &&
    (interval.min === null || value >= interval.min) &&
    (interval.max === null || value < interval.max)
  )
}
