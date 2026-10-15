import { describe, expect, it } from 'vitest'
import { createSelectionMockHandlers } from '../api/selection-mock-handlers'
import {
  comparablePreviousRank,
  rankChange,
  discoveryLabels,
  discoveryDescriptions,
  categoryLeaf,
  sourceProductUrl,
  formatCandidateTime,
  formatFirstListed,
} from './candidate-display'

describe('candidate rank and discovery semantics', () => {
  it.each([
    [true, '是'],
    [false, '否'],
    [null, '—'],
  ] as const)(
    'preserves platform first-listed state %s as %s',
    (value, label) => {
      expect(formatFirstListed(value)).toBe(label)
    },
  )
  it('compares only the same leaderboard/scope and never turns scope exit into delisting', async () => {
    const service = createSelectionMockHandlers()
    const row = await service.candidate('candidate-001')
    expect(comparablePreviousRank(row)).toBe(4)
    expect(rankChange(row)).toEqual({ label: '↑ 2', type: 'success' })
    expect(rankChange({ ...row, rank: 6 })).toEqual({
      label: '↓ 2',
      type: 'error',
    })
    expect(rankChange({ ...row, rank: 4 })).toEqual({ label: '持平' })
    expect(rankChange({ ...row, rank: null })).toBeNull()
    expect(
      rankChange({
        ...row,
        previousRank: { ...row.previousRank!, leaderboardId: 'other' },
      }),
    ).toBeNull()
    expect(rankChange(await service.candidate('candidate-003'))).toBeNull()
    const newToScope = await service.candidate('candidate-004')
    expect(newToScope.discovery).toBe('new-in-scope')
    expect(newToScope.firstListed).toBe(false)
    expect(discoveryLabels['new-in-scope']).toBe('新进入')
    expect(discoveryLabels['outside-scope']).toBe('已离开')
    expect(Object.values(discoveryLabels).join()).not.toContain('下榜')
    expect(discoveryDescriptions['new-in-scope']).toContain(
      '不等同于平台首次上榜',
    )
    expect(discoveryDescriptions['outside-scope']).toContain('不代表已下榜')
  })
  it('renders only the category leaf without changing the stored path', () => {
    const path = '服饰 / 女装 / 连衣裙'
    expect(categoryLeaf(path)).toBe('连衣裙')
    expect(categoryLeaf('')).toBe('—')
    expect(categoryLeaf('家居')).toBe('家居')
    expect(path).toBe('服饰 / 女装 / 连衣裙')
  })
  it('only exposes supplied safe source links, without guessing product URLs', () => {
    expect(sourceProductUrl(null)).toBeNull()
    expect(sourceProductUrl('javascript:alert(1)')).toBeNull()
    expect(sourceProductUrl('https://user:password@example.test')).toBeNull()
    expect(sourceProductUrl('https://example.test/products/123')).toBe(
      'https://example.test/products/123',
    )
  })
  it('uses the existing timestamp formatter for compact metadata without inventing a missing time', () => {
    const value = '2026-10-09T23:27:00'
    expect(formatCandidateTime(value)).toBe('2026-10-09 23:27')
    expect(formatCandidateTime(value, 'MM-DD HH:mm')).toBe('10-09 23:27')
    expect(formatCandidateTime(null, 'MM-DD HH:mm')).toBe('—')
  })
})
