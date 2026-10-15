import type { LocationQuery, LocationQueryRaw } from 'vue-router'
import type { CandidateQuery } from './contracts'
import type { SelectionResultScope } from '../api/selection-read-api'

const DEFAULT_CANDIDATE_PAGE_SIZE = 20

const scalar = (query: LocationQuery, name: string) =>
  typeof query[name] === 'string' ? (query[name] as string) : null
const number = (value: string | null, fallback: number) =>
  value && /^[1-9][0-9]*$/.test(value) ? Number(value) : fallback
export function candidateFilters(query: LocationQuery): CandidateQuery {
  const sort = scalar(query, 'candidate_sort')
  return {
    page: number(scalar(query, 'candidate_page'), 1),
    pageSize: number(
      scalar(query, 'candidate_size'),
      DEFAULT_CANDIDATE_PAGE_SIZE,
    ),
    shopId: scalar(query, 'request_shop'),
    keyword: scalar(query, 'candidate_search') ?? '',
    blocked: scalar(query, 'blocked') === '1',
    resultScope: (scalar(query, 'result_scope') ??
      'all') as SelectionResultScope,
    strategyId: scalar(query, 'strategy_id'),
    receiptId: scalar(query, 'receipt_id'),
    sortField:
      sort === 'listedAt' || sort === 'negativeReviewRate' ? sort : null,
    sortOrder: sort
      ? scalar(query, 'candidate_order') === 'ascend'
        ? 'ascend'
        : 'descend'
      : false,
  }
}
export function candidateRoute(query: CandidateQuery): LocationQueryRaw {
  return {
    candidate_page: query.page === 1 ? undefined : String(query.page),
    candidate_size:
      query.pageSize === DEFAULT_CANDIDATE_PAGE_SIZE
        ? undefined
        : String(query.pageSize),
    request_shop: query.shopId ?? undefined,
    candidate_search: query.keyword || undefined,
    blocked: query.blocked ? '1' : undefined,
    result_scope: query.resultScope === 'all' ? undefined : query.resultScope,
    strategy_id: query.strategyId ?? undefined,
    receipt_id: query.receiptId ?? undefined,
    candidate_sort: query.sortField ?? undefined,
    candidate_order: query.sortOrder || undefined,
  }
}
