import { describe, expect, it } from 'vitest'
import { candidateFilters, candidateRoute } from './candidate-query'
import type { LocationQuery } from 'vue-router'
describe('candidate result route contract', () => {
  it('defaults only missing or invalid page sizes to 20 and omits that default from the route', () => {
    expect(candidateFilters({}).pageSize).toBe(20)
    for (const candidate_size of ['', '0', '-1', 'invalid'])
      expect(candidateFilters({ candidate_size }).pageSize).toBe(20)
    expect(candidateRoute(candidateFilters({})).candidate_size).toBeUndefined()
  })
  it.each(['10', '20', '50', '100'])(
    'retains an explicit page size %s through route persistence',
    (candidate_size) => {
      const filter = candidateFilters({
        candidate_size,
        candidate_page: '2',
        candidate_search: '保留筛选',
        candidate_sort: 'listedAt',
        candidate_order: 'ascend',
      })
      expect(filter.pageSize).toBe(Number(candidate_size))
      expect(candidateFilters(candidateRoute(filter) as LocationQuery)).toEqual(
        filter,
      )
      if (candidate_size !== '20')
        expect(candidateRoute(filter).candidate_size).toBe(candidate_size)
    },
  )
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
