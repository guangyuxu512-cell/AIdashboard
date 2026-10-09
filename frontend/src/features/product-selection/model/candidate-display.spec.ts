import { describe, expect, it } from 'vitest'
import { createSelectionMockHandlers } from '../api/selection-mock-handlers'
import {
  comparablePreviousRank,
  rankChangeLabel,
  discoveryLabels,
  sourceProductUrl,
} from './candidate-display'

describe('candidate rank and discovery semantics', () => {
  it('compares only the same leaderboard/scope and never turns scope exit into delisting', async () => {
    const service = createSelectionMockHandlers()
    const row = await service.candidate('candidate-001')
    expect(comparablePreviousRank(row)).toBe(4)
    expect(rankChangeLabel(row)).toBe('上升 2')
    expect(rankChangeLabel({ ...row, rank: 6 })).toBe('下降 2')
    expect(rankChangeLabel({ ...row, rank: 4 })).toBe('持平')
    expect(rankChangeLabel({ ...row, rank: null })).toBeNull()
    expect(
      rankChangeLabel({
        ...row,
        previousRank: { ...row.previousRank!, leaderboardId: 'other' },
      }),
    ).toBeNull()
    expect(rankChangeLabel(await service.candidate('candidate-003'))).toBeNull()
    const newToScope = await service.candidate('candidate-004')
    expect(newToScope.discovery).toBe('new-in-scope')
    expect(newToScope.firstListed).toBe(false)
    expect(discoveryLabels['outside-scope']).toBe('离开监控范围')
    expect(Object.values(discoveryLabels).join()).not.toContain('下榜')
  })
  it('only exposes supplied safe source links, without guessing product URLs', () => {
    expect(sourceProductUrl(null)).toBeNull()
    expect(sourceProductUrl('javascript:alert(1)')).toBeNull()
    expect(sourceProductUrl('https://user:password@example.test')).toBeNull()
    expect(sourceProductUrl('https://example.test/products/123')).toBe(
      'https://example.test/products/123',
    )
  })
})
