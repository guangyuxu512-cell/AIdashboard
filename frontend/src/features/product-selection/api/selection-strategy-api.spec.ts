import { beforeEach, describe, expect, it, vi } from 'vitest'
import { httpClient } from '@/shared/api'
import {
  createSelectionRealService,
  mapSelectionStrategy,
} from './selection-real-service'
import type { SelectionStrategyDto } from './selection-strategy-api'
import { emptyStrategy, type CategoryNode } from '../model/contracts'

vi.mock('@/shared/api', () => ({
  httpClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn() },
}))

function saved(): SelectionStrategyDto {
  return {
    strategy_id: 'strategy-a',
    team_id: 'team-a',
    created_by_user_id: 'user-a',
    version: 3,
    name: '数据库策略',
    shop_id: 'shop-a',
    shop_name: '请求自有店铺',
    enabled: true,
    conditions: {
      version: 1,
      request: {
        channel: 'short-video',
        period: '7d',
        industry_id: '7',
        category_ids: ['1001'],
        brand: 'all',
        price_mode: 'all',
        price_above: null,
        price_below: null,
        first_listed_only: true,
        rank_from: 151,
        rank_to: 200,
      },
    },
    schedule: {
      scheduled: true,
      kind: 'daily',
      daily_time: '10:30',
      timezone: 'Asia/Shanghai',
    },
    schedule_available: false,
    next_run_at: null,
    latest_run: null,
    created_at: '2026-10-13T00:00:00Z',
    updated_at: '2026-10-13T01:00:00Z',
  }
}
const tree: CategoryNode[] = [
  {
    id: '7',
    name: '实际行业',
    children: [
      {
        id: '7/1001',
        name: '真实父类目',
        requestScope: { industryId: '7', categoryIds: ['1001'] },
      },
    ],
  },
]
const unavailable = async (): Promise<never> => {
  throw new Error('未接入')
}

describe('saved Real strategies use the registered backend contract', () => {
  beforeEach(() => vi.clearAllMocks())
  it('maps only saved values and does not manufacture a next occurrence or recent result', () => {
    const dto = saved()
    const view = mapSelectionStrategy(dto)
    expect(view.version).toBe(3)
    expect(view.creatorId).toBeNull()
    expect(view.channels.shortVideo.conditions.categoryId).toBe('7/1001')
    expect(view.channels.shortVideo.conditions.firstListedOnly).toBe(true)
    expect(view.scheduled).toBe(true)
    expect(view.dailyTime).toBe('10:30')
    expect(view.scheduleAvailable).toBe(false)
    expect(view.latestResult).toBeNull()
    expect(view.nextRunAt).toBeNull()
  })
  it('reads a server-filtered page and never submits a platform run on refresh', async () => {
    const real = createSelectionRealService(unavailable)
    vi.mocked(httpClient.get).mockResolvedValueOnce({
      data: { items: [saved()], total: 31, page: 2, page_size: 10 },
    })
    const result = await real.strategiesPage!({
      page: 2,
      pageSize: 10,
      search: '数据库',
    })
    expect(result.total).toBe(31)
    expect(httpClient.get).toHaveBeenCalledWith(
      '/api/v1/product-selection/strategies',
      { params: { page: 2, page_size: 10, search: '数据库' } },
    )
    expect(httpClient.post).not.toHaveBeenCalled()
    expect(real.available).toBe(false) // Phone/material actions still unavailable.
    expect(real.strategySaveAvailable).toBe(true)
  })
  it('saving and toggling only write configuration, preserve relative period and CAS version', async () => {
    const real = createSelectionRealService(unavailable)
    const row = mapSelectionStrategy(saved())
    vi.mocked(httpClient.put).mockResolvedValueOnce({ data: saved() })
    await real.saveStrategy(
      { ...row, name: '仅保存草稿' },
      row.id,
      row.version,
      tree,
    )
    const [url, body] = vi.mocked(httpClient.put).mock.calls[0]!
    expect(url).toBe('/api/v1/product-selection/strategies/strategy-a')
    expect(body).toMatchObject({
      expected_version: 3,
      name: '仅保存草稿',
      conditions: {
        request: { period: '7d', rank_to: 200, first_listed_only: true },
      },
    })
    expect(JSON.stringify(body)).not.toContain('begin_date')
    vi.mocked(httpClient.patch).mockResolvedValueOnce({
      data: { ...saved(), enabled: false, version: 4 },
    })
    expect((await real.toggleStrategy!(row, false)).enabled).toBe(false)
    expect(httpClient.patch).toHaveBeenCalledWith(
      '/api/v1/product-selection/strategies/strategy-a/enabled',
      { enabled: false, expected_version: 3 },
    )
    expect(httpClient.post).not.toHaveBeenCalled()
    expect(httpClient.get).not.toHaveBeenCalled()
  })
  it('immediate retrieve binds saved identity/version but never saves submitted draft changes', async () => {
    const real = createSelectionRealService(unavailable)
    const row = mapSelectionStrategy(saved())
    vi.mocked(httpClient.post).mockResolvedValueOnce({
      data: { execution_run_id: 'run-a' },
    })
    await real.manual!.submit(
      { ...row, name: '未保存修改' },
      'stable-key',
      tree,
      { id: row.id, version: row.version! },
    )
    expect(httpClient.post).toHaveBeenCalledWith(
      '/api/v1/product-selection/runs',
      expect.objectContaining({
        strategy_id: 'strategy-a',
        strategy_version: 3,
        submission_key: 'stable-key',
        rank_from: 151,
        rank_to: 200,
        first_listed_only: true,
      }),
    )
    expect(httpClient.put).not.toHaveBeenCalled()
    expect(
      JSON.stringify(vi.mocked(httpClient.post).mock.calls[0]),
    ).not.toContain('未保存修改')
    const draft = emptyStrategy()
    draft.shopId = row.shopId
    draft.channels.shortVideo.conditions = row.channels.shortVideo.conditions
    vi.mocked(httpClient.post).mockResolvedValueOnce({
      data: { execution_run_id: 'run-b' },
    })
    await real.manual!.submit(draft, 'new-key', tree)
    expect(vi.mocked(httpClient.post).mock.calls[1]![1]).not.toHaveProperty(
      'strategy_id',
    )
  })
  it('a non-wrapped category tree restores the exact saved scope, without guessing IDs', async () => {
    const real = createSelectionRealService(unavailable)
    const row = mapSelectionStrategy(saved())
    vi.mocked(httpClient.get).mockResolvedValueOnce({
      data: {
        shop_id: 'shop-a',
        industry_id: '7',
        nodes: [{ category_id: '1001', name: '父类目', children: [] }],
      },
    })
    vi.mocked(httpClient.post).mockResolvedValueOnce({
      data: { execution_run_id: 'run-a' },
    })
    await real.manual!.submit(row, 'key')
    expect(httpClient.post).toHaveBeenCalledWith(
      '/api/v1/product-selection/runs',
      expect.objectContaining({ industry_id: '7', category_ids: ['1001'] }),
    )
  })
})
