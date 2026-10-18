import { describe, expect, it } from 'vitest'
import { PRODUCT_DISPLAY_COLUMNS } from './display-fields'
import { cloneProductFilters, emptyProductFilters } from './query'
import {
  PRODUCT_RANGE_FILTERS,
  compileProductRanges,
  emptyProductRangeDrafts,
  matchesProductInterval,
  productRangeOptions,
  selectProductRange,
  type ProductRangeChoice,
} from './metric-ranges'
import type { ProductMetric } from './types'

describe('product metric interval draft contract', () => {
  it('uses the approved core display metadata as its only presentation order', () => {
    expect(PRODUCT_RANGE_FILTERS.map(({ id }) => id)).toEqual(
      PRODUCT_DISPLAY_COLUMNS.filter(({ group }) => group === 'core').map(
        ({ id }) => id,
      ),
    )
  })

  it('defaults every field to unlimited with isolated draft objects', () => {
    const first = emptyProductFilters(),
      second = emptyProductFilters()
    expect(Object.keys(first.metricRanges)).toHaveLength(9)
    expect(compileProductRanges(first.metricRanges)).toEqual({
      intervals: [],
      errors: {},
    })
    first.metricRanges.exposureCount.min = 5
    expect(second.metricRanges.exposureCount.min).toBeNull()
    const copy = cloneProductFilters(first)
    first.metricRanges.exposureCount.min = 99
    expect(copy.metricRanges.exposureCount.min).toBe(5)
  })

  it.each(PRODUCT_RANGE_FILTERS)(
    'partitions every preset edge once, without overlap or gaps: $id',
    (field) => {
      const intervals = field.boundaries.map((_, index) => {
        const drafts = emptyProductRangeDrafts()
        drafts[field.id] = {
          choice: ('preset-' + index) as ProductRangeChoice,
          min: null,
          max: null,
        }
        return compileProductRanges(drafts).intervals[0]!
      })
      expect(productRangeOptions(field.id)).toHaveLength(7)
      expect(intervals.at(-1)!.max).toBeNull()
      for (const [index, edge] of field.boundaries.entries()) {
        const divisor = field.percent ? 100 : 1
        const metric: ProductMetric = {
          state: 'available',
          value: String(edge / divisor),
          unit: field.percent ? 'ratio' : 'count',
        }
        expect(
          intervals.flatMap((range, n) =>
            matchesProductInterval(metric, range) ? [n] : [],
          ),
        ).toEqual([index])
        if (index > 0) {
          const below = {
            ...metric,
            value: String((edge - (field.percent ? 0.001 : 1)) / divisor),
          }
          expect(
            intervals.flatMap((range, n) =>
              matchesProductInterval(below, range) ? [n] : [],
            ),
          ).toEqual([index - 1])
        }
      }
      const after = {
        state: 'available',
        value: String(
          (field.boundaries.at(-1)! + 1000) / (field.percent ? 100 : 1),
        ),
        unit: field.percent ? 'ratio' : 'count',
      } as ProductMetric
      expect(
        intervals.filter((range) => matchesProductInterval(after, range)),
      ).toEqual([intervals.at(-1)])
    },
  )

  it.each(PRODUCT_RANGE_FILTERS)(
    'accepts empty or valid one-sided custom bounds: $id',
    (field) => {
      const drafts = emptyProductRangeDrafts()
      drafts[field.id] = { choice: 'custom', min: null, max: null }
      expect(compileProductRanges(drafts).intervals).toEqual([])
      for (const bounds of [
        { min: 5, max: null },
        { min: null, max: 10 },
        { min: 0, max: 10 },
      ]) {
        drafts[field.id] = { choice: 'custom', ...bounds }
        const result = compileProductRanges(drafts),
          divisor = field.percent ? 100 : 1
        expect(result.errors).toEqual({})
        expect(result.intervals[0]).toMatchObject({
          metricId: field.id,
          min: bounds.min === null ? null : bounds.min / divisor,
          max: bounds.max === null ? null : bounds.max / divisor,
          minInclusive: true,
          maxInclusive: false,
          unit: field.percent ? 'fraction' : 'count',
        })
      }
    },
  )

  it.each(PRODUCT_RANGE_FILTERS)(
    'rejects negative, inverted, equal and non-finite bounds: $id',
    (field) => {
      for (const bounds of [
        { min: -1, max: null },
        { min: null, max: -1 },
        { min: 10, max: 5 },
        { min: 5, max: 5 },
        { min: NaN, max: null },
        { min: null, max: Infinity },
      ]) {
        const drafts = emptyProductRangeDrafts()
        drafts[field.id] = { choice: 'custom', ...bounds }
        expect(compileProductRanges(drafts).errors[field.id]).toBeTruthy()
      }
    },
  )

  it('does not inherit stale custom bounds into a preset or clear action', () => {
    expect(
      selectProductRange('preset-1', { choice: 'custom', min: 7, max: 9 }),
    ).toEqual({ choice: 'preset-1', min: null, max: null })
    expect(
      selectProductRange(null, { choice: 'custom', min: 7, max: 9 }),
    ).toEqual({ choice: 'unlimited', min: null, max: null })
    const draft = emptyProductRangeDrafts()
    draft.exposureCount = { choice: 'custom', min: 1.5, max: null }
    expect(compileProductRanges(draft).errors.exposureCount).toContain('整数')
    draft.exposureCount.choice = 'unlimited'
    draft.clickPayRate = { choice: 'custom', min: 4.5, max: 6 }
    expect(compileProductRanges(draft).intervals[0]).toMatchObject({
      min: 0.045,
      max: 0.06,
    })
  })

  it('uses the continuous 2–4%, 4–6% conversion presets including the former screenshot gap', () => {
    const drafts = emptyProductRangeDrafts()
    drafts.clickPayRate = {
      choice: 'preset-3',
      min: null,
      max: null,
    }
    const interval = compileProductRanges(drafts).intervals[0]!
    for (const value of ['0.04', '0.045', '0.05', '0.05999'])
      expect(
        matchesProductInterval(
          { state: 'available', value, unit: 'ratio' },
          interval,
        ),
      ).toBe(true)
    expect(
      matchesProductInterval(
        { state: 'available', value: '0.06', unit: 'ratio' },
        interval,
      ),
    ).toBe(false)
  })

  it('does not coerce absent, sentinel, invalid or wrong-unit values into the zero bucket', () => {
    const drafts = emptyProductRangeDrafts()
    drafts.exposureCount = { choice: 'preset-0', min: null, max: null }
    const interval = compileProductRanges(drafts).intervals[0]!
    expect(
      matchesProductInterval(
        { state: 'available', value: '0', unit: 'count' },
        interval,
      ),
    ).toBe(true)
    for (const state of ['missing', 'null', 'invalid'] as const)
      expect(
        matchesProductInterval({ state, value: '0', unit: 'count' }, interval),
      ).toBe(false)
    for (const value of [null, '', ' ', '-1', 'NaN', 'Infinity'])
      expect(
        matchesProductInterval(
          { state: 'available', value, unit: 'count' },
          interval,
        ),
      ).toBe(false)
    expect(
      matchesProductInterval(
        { state: 'available', value: '0', unit: null },
        interval,
      ),
    ).toBe(false)
  })
})
