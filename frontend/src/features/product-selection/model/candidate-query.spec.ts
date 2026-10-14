import { describe, expect, it } from 'vitest'
import { candidateFilters, candidateRoute } from './candidate-query'
import type { LocationQuery } from 'vue-router'
describe('candidate result route contract', () => {
  it('round trips shop/result/strategy/batch/sort/page without turning a malformed resource into all', () => {
    const filter = candidateFilters({
      result_scope: 'today_new',
      strategy_id: 'strategy',
      receipt_id: 'receipt',
      request_shop: 'shop',
      candidate_page: '2',
      candidate_search: '19位ID',
      blocked: '1',
      candidate_sort: 'listedAt',
      candidate_order: 'ascend',
    })
    expect(candidateFilters(candidateRoute(filter) as LocationQuery)).toEqual(
      filter,
    )
    expect(candidateFilters({ strategy_id: 'not-a-uuid' }).strategyId).toBe(
      'not-a-uuid',
    )
    expect(candidateFilters({}).shopId).toBeNull()
  })
})
