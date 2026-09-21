import type { DashboardComparison, MerchantExperienceScore } from './types'

const currencyFormatter = new Intl.NumberFormat('zh-CN', {
  style: 'currency',
  currency: 'CNY',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const dateTimeFormatter = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

export function formatDashboardCurrency(value: number | null): string {
  return value === null ? '—' : currencyFormatter.format(value / 100)
}

export function formatDashboardCount(value: number | null): string {
  return value === null ? '—' : new Intl.NumberFormat('zh-CN').format(value)
}

export function formatDashboardCollectedAt(value: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : dateTimeFormatter.format(date)
}

export function formatDashboardComparison(comparison: DashboardComparison): string {
  if (comparison.state === 'unavailable') return '—'
  if (comparison.state === 'equal') return '持平'
  const sign = comparison.state === 'increase' ? '+' : '-'
  const arrow = comparison.state === 'increase' ? '▲' : '▼'
  return `${sign}${comparison.percentage.toFixed(1)}% ${arrow}`
}

export function getDashboardComparisonTone(
  comparison: DashboardComparison,
): 'positive' | 'negative' | 'neutral' {
  if (comparison.state === 'unavailable' || comparison.state === 'equal') {
    return 'neutral'
  }
  return comparison.favorable ? 'positive' : 'negative'
}

export function formatMerchantExperience(
  experience: MerchantExperienceScore | null,
): string {
  if (!experience) return '—'
  return `${experience.totalScore}分 商品${experience.productScore ?? '—'} · 物流${experience.logisticsScore ?? '—'} · 服务${experience.serviceScore ?? '—'}`
}
