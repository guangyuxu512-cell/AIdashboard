import { beforeEach, describe, expect, it, vi } from 'vitest'
import { httpClient } from '@/shared/api'
import {
  readSelectionCandidates,
  readSelectionObservation,
  readLatestSelectionRun,
  readSelectionCategories,
  readSelectionRun,
} from './selection-read-api'

vi.mock('@/shared/api', () => ({ httpClient: { get: vi.fn() } }))

describe('registered selection database read API', () => {
  beforeEach(() => vi.clearAllMocks())

  it('reads a submitted run by exact ID and only forces categories on an explicit refresh', async () => {
    const tree = { shop_id: 'authorized-shop', nodes: [] }
    vi.mocked(httpClient.get).mockResolvedValue({ data: tree })
    await readSelectionCategories('authorized-shop')
    expect(httpClient.get).toHaveBeenLastCalledWith(
      '/api/v1/product-selection/categories',
      { params: { shop_id: 'authorized-shop' } },
    )
    await readSelectionCategories('authorized-shop', { refresh: true })
    expect(httpClient.get).toHaveBeenLastCalledWith(
      '/api/v1/product-selection/categories',
      { params: { shop_id: 'authorized-shop', refresh: true } },
    )
    const run = { run_id: 'current-run', status: 'pending' }
    vi.mocked(httpClient.get).mockResolvedValueOnce({ data: run })
    expect(await readSelectionRun('current-run')).toBe(run)
    expect(httpClient.get).toHaveBeenLastCalledWith(
      '/api/v1/product-selection/runs/current-run',
    )
  })

  it('sends only declared filters with explicit ten-row pagination', async () => {
    const page = { items: [], total: 0, page: 2, page_size: 10 }
    vi.mocked(httpClient.get).mockResolvedValueOnce({ data: page })
    expect(
      await readSelectionCandidates({
        page: 2,
        pageSize: 10,
        shopId: 'request-shop',
        sourceScopeHash: 'scope-hash',
        search: '19位ID%',
        sortField: 'first_on_shelf_date',
        sortDirection: 'asc',
      }),
    ).toBe(page)
    expect(httpClient.get).toHaveBeenCalledExactlyOnceWith(
      '/api/v1/product-selection/candidates',
      {
        params: {
          page: 2,
          page_size: 10,
          shop_id: 'request-shop',
          source_scope_hash: 'scope-hash',
          search: '19位ID%',
          sort_field: 'first_on_shelf_date',
          sort_direction: 'asc',
        },
      },
    )
  })

  it('preserves string product IDs, raw decimals, null and both source times', async () => {
    const dto = {
      product_id: '3769776708757094595',
      request_shop_id: 'own-shop',
      merchants: [{ platform_shop_id: '239490763', name: '商品商家' }],
      bad_comment_rate_raw: '0.00205018686599039',
      bad_comment_rate_unit: 4,
      rank: 0,
      category_path: null,
      checked_at: '2026-10-10T07:30:00Z',
      metrics_retrieved_at: '2026-10-10T07:30:01Z',
      video_metric_ranges: {
        pay_amt: {
          state: 'available',
          value_range: [
            { value: '10000000', value_type: 'int', unit: 'price' },
            { value: '25000000', value_type: 'int', unit: 'price' },
          ],
        },
      },
    }
    vi.mocked(httpClient.get).mockResolvedValueOnce({ data: dto })
    expect(await readSelectionObservation('observation-id')).toBe(dto)
    expect(httpClient.get).toHaveBeenCalledExactlyOnceWith(
      '/api/v1/product-selection/observations/observation-id',
    )
  })

  it('does not turn authentication, business failure or malformed results into Mock/empty success', async () => {
    const failure = new Error('模块访问已撤销')
    vi.mocked(httpClient.get).mockRejectedValueOnce(failure)
    await expect(
      readSelectionCandidates({ page: 1, pageSize: 10 }),
    ).rejects.toBe(failure)
    expect(httpClient.get).toHaveBeenCalledTimes(1)
  })
  it('reads canonical execution status without creating an execution or a receipt', async () => {
    const run = { run_id: 'canonical', status: 'succeeded', result_count: 0 }
    vi.mocked(httpClient.get)
      .mockResolvedValueOnce({ data: { items: [run] } })
      .mockResolvedValueOnce({ data: { items: [] } })
    expect(await readLatestSelectionRun('authorized-shop')).toBe(run)
    expect(httpClient.get).toHaveBeenCalledWith(
      '/api/v1/product-selection/runs',
      { params: { shop_id: 'authorized-shop', page: 1, page_size: 1 } },
    )
    expect(await readLatestSelectionRun(null)).toBeNull()
  })
})
