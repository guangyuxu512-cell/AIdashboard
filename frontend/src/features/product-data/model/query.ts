import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'
import timezone from 'dayjs/plugin/timezone'
import { z } from 'zod'
import { emptyProductRangeDrafts } from './metric-ranges'
import type { ProductDataFilters, ProductDataRow, ProductMetric } from './types'

dayjs.extend(utc)
dayjs.extend(timezone)

export function emptyProductFilters(): ProductDataFilters {
  return {
    shopId: null,
    productId: '',
    productName: '',
    groupId: null,
    selling: null,
    carrier: null,
    datePreset: 'yesterday',
    customDateRange: null,
    metricRanges: emptyProductRangeDrafts(),
  }
}
export function cloneProductFilters(
  filters: ProductDataFilters,
): ProductDataFilters {
  return {
    ...filters,
    customDateRange: filters.customDateRange
      ? [...filters.customDateRange]
      : null,
    metricRanges: Object.fromEntries(
      Object.entries(filters.metricRanges).map(([id, range]) => [
        id,
        { ...range },
      ]),
    ) as ProductDataFilters['metricRanges'],
  }
}
export function productPeriod(
  filters: ProductDataFilters,
  now: Date = new Date(),
): ProductDataRow['period'] {
  if (filters.datePreset === 'custom') {
    if (!filters.customDateRange) throw new Error('请选择统计日期')
    const [start, end] = filters.customDateRange
    if (!Number.isFinite(start) || !Number.isFinite(end) || start > end)
      throw new Error('统计日期范围无效')
    return {
      startDate: dayjs(start).tz('Asia/Shanghai').format('YYYY-MM-DD'),
      endDate: dayjs(end).tz('Asia/Shanghai').format('YYYY-MM-DD'),
    }
  }
  const end = dayjs(now).tz('Asia/Shanghai').startOf('day').subtract(1, 'day')
  const count =
    filters.datePreset === 'last30Days'
      ? 30
      : filters.datePreset === 'last7Days'
        ? 7
        : 1
  return {
    startDate: end.subtract(count - 1, 'day').format('YYYY-MM-DD'),
    endDate: end.format('YYYY-MM-DD'),
  }
}
export const productGroupNameSchema = z
  .string()
  .trim()
  .min(1, '请输入分组名称')
  .max(40, '分组名称最多40字')
export const PRODUCT_METRIC_STATE_LABELS = {
  available: '已取得',
  missing: '未取得',
  null: '平台返回空值',
  invalid: '平台值无效',
} as const

export function formatProductMetric(metric: ProductMetric): string {
  if (metric.state !== 'available' || metric.value === null) return '—'
  const numeric = Number(metric.value)
  if (!Number.isFinite(numeric)) return '—'
  if (metric.unit === 'ratio') return (numeric * 100).toFixed(2) + '%'
  if (metric.unit === 'yuan')
    return (
      '¥' +
      numeric.toLocaleString('zh-CN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })
    )
  return numeric.toLocaleString('zh-CN')
}
