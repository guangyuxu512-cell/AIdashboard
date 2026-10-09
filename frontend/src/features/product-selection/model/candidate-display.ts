import dayjs from 'dayjs'
import type {
  CandidateDiscovery,
  MaterialCollectionStatus,
  SelectionCandidate,
} from './contracts'

// List and detail use the same nullable value formatting; zero is not missing.
export const formatCandidateDate = (value: string | null) =>
  value === null ? '—' : dayjs(value).format('YYYY-MM-DD')
export const formatReviewRate = (value: number | null) =>
  value === null ? '—' : `${(value * 100).toFixed(2)}%`

export const formatCandidateTime = (value: string | null) =>
  value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '—'

export function comparablePreviousRank(row: SelectionCandidate): number | null {
  const previous = row.previousRank
  return previous &&
    previous.leaderboardId === row.sourceContext.leaderboardId &&
    previous.scopeKey === row.sourceContext.scopeKey
    ? previous.rank
    : null
}

export function rankChangeLabel(row: SelectionCandidate): string | null {
  const previous = comparablePreviousRank(row)
  if (previous === null || row.rank === null) return null
  const change = previous - row.rank
  return change === 0
    ? '持平'
    : `${change > 0 ? '上升' : '下降'} ${Math.abs(change)}`
}

export const discoveryLabels: Record<CandidateDiscovery, string> = {
  'new-in-scope': '新进入监控范围',
  known: '已发现',
  'outside-scope': '离开监控范围',
  unknown: '—',
}
export const collectionLabels: Record<MaterialCollectionStatus, string> = {
  'not-collected': '未采集',
  'demo-collected': '已演示采集',
  failed: '采集失败',
  unknown: '—',
}

export function sourceProductUrl(value: string | null): string | null {
  if (!value) return null
  try {
    const url = new URL(value)
    return ['https:', 'http:'].includes(url.protocol) &&
      !url.username &&
      !url.password
      ? url.href
      : null
  } catch {
    return null
  }
}
