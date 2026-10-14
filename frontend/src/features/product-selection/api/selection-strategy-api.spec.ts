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
  it('reads real next time and trigger failure without inventing a zero-result run', () => {
    const dto = saved()
    dto.schedule_available = true
    dto.schedule_execution_enabled = false
    dto.schedule = { ...dto.schedule, kind: 'hourly', interval_hours: 5 }
    dto.next_run_at = '2026-10-14T06:00:00Z'
    dto.latest_trigger = {
      schedule_run_id: 'audit',
      scheduled_for: '2026-10-14T01:00:00Z',
      created_at: '2026-10-14T01:01:00Z',
      trigger_result: 'blocked',
      receipt_id: null,
      execution_run_id: null,
      error_code: 'SHOP_SESSION_AUTHENTICATION_INVALID',
      error_stage: 'session',
    }
    const view = mapSelectionStrategy(dto)
    expect(view.hourlyInterval).toBe(5)
    expect(view.nextRunAt).toBe(dto.next_run_at)
    expect(view.scheduleExecutionEnabled).toBe(false)
    expect(view.latestExecution).toBeNull()
    expect(view.latestResult).toBe('触发失败 · 店铺登录已失效，请重新登录')
    expect(httpClient.post).not.toHaveBeenCalled()
  })
  beforeEach(() => vi.clearAllMocks())
  it.each([
    ['known', false],
    ['unknown', false],
    ['known', true],
    ['unknown', true],
  ] as const)(
    'persists/rereads and executes confirmed brand %s with custom=%s',
    async (brand, custom) => {
      const service = createSelectionRealService(unavailable)
      const dto = saved()
      dto.conditions.request.brand = brand
      if (custom)
        Object.assign(dto.conditions.request, {
          price_mode: 'custom',
          price_above: '20',
          price_below: '100',
        })
      const input = mapSelectionStrategy(dto)
      vi.mocked(httpClient.put).mockResolvedValueOnce({ data: dto })
      const read = await service.saveStrategy(
        input,
        input.id,
        input.version,
        tree,
      )
      expect(read.channels.shortVideo.conditions.brand).toBe(brand)
      expect(httpClient.put).toHaveBeenLastCalledWith(
        '/api/v1/product-selection/strategies/strategy-a',
        expect.objectContaining({
          conditions: {
            version: 1,
            request: expect.objectContaining({
              brand,
              price_mode: custom ? 'custom' : 'all',
            }),
          },
        }),
      )
      vi.mocked(httpClient.post).mockResolvedValueOnce({
        data: { receipt_id: 'brand-run' },
      })
      await service.manual!.submit(read, 'brand-key', tree, {
        id: read.id,
        version: read.version!,
      })
      expect(httpClient.post).toHaveBeenLastCalledWith(
        '/api/v1/product-selection/runs',
        expect.objectContaining({ brand, strategy_id: 'strategy-a' }),
      )
      expect(httpClient.put).toHaveBeenCalledOnce()
      read.channels.shortVideo.conditions.brand = '0' as never
      await expect(
        service.manual!.submit(read, 'bad-brand-key', tree),
      ).rejects.toThrow('未确认')
      expect(httpClient.post).toHaveBeenCalledOnce()
    },
  )
  it('saves/rereads custom yuan values and executes draft bounds without changing the saved strategy', async () => {
    const service = createSelectionRealService(unavailable)
    const dto = saved()
    Object.assign(dto.conditions.request, {
      price_mode: 'custom',
      price_above: '20.00',
      price_below: '100.0',
    })
    const input = mapSelectionStrategy(dto)
    vi.mocked(httpClient.put).mockResolvedValueOnce({ data: dto })
    const read = await service.saveStrategy(
      input,
      input.id,
      input.version,
      tree,
    )
    expect(read.channels.shortVideo.conditions.priceAbove).toBe(20)
    expect(read.channels.shortVideo.conditions.priceBelow).toBe(100)
    expect(httpClient.put).toHaveBeenLastCalledWith(
      '/api/v1/product-selection/strategies/strategy-a',
      expect.objectContaining({
        conditions: {
          version: 1,
          request: expect.objectContaining({
            price_mode: 'custom',
            price_above: '20',
            price_below: '100',
          }),
        },
      }),
    )
    read.channels.shortVideo.conditions.priceBelow = 40
    vi.mocked(httpClient.post).mockResolvedValueOnce({
      data: { receipt_id: 'price-run' },
    })
    await service.manual!.submit(read, 'price-key', tree, {
      id: read.id,
      version: read.version!,
    })
    expect(httpClient.post).toHaveBeenLastCalledWith(
      '/api/v1/product-selection/runs',
      expect.objectContaining({
        price_mode: 'custom',
        price_above: '20',
        price_below: '40',
        strategy_id: read.id,
      }),
    )
    expect(httpClient.put).toHaveBeenCalledOnce()
    for (const [lower, upper] of [
      [null, 100],
      [20, null],
      [100, 20],
      [20.001, 100],
    ]) {
      Object.assign(read.channels.shortVideo.conditions, {
        priceAbove: lower,
        priceBelow: upper,
      })
      await expect(
        service.manual!.submit(read, 'bad-key', tree),
      ).rejects.toThrow('价格')
    }
    expect(httpClient.post).toHaveBeenCalledOnce()
    Object.assign(read.channels.shortVideo.conditions, {
      priceMode: 'all',
      priceAbove: 20,
      priceBelow: 40,
    })
    vi.mocked(httpClient.post).mockResolvedValueOnce({
      data: { receipt_id: 'all-run' },
    })
    await service.manual!.submit(read, 'all-key', tree)
    expect(httpClient.post).toHaveBeenLastCalledWith(
      '/api/v1/product-selection/runs',
      expect.objectContaining({
        price_mode: 'all',
        price_above: null,
        price_below: null,
      }),
    )
  })
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
  it.each([1, 2, 3, 5, 6, 12])(
    'preserves every %i hours through save and edit read without executing',
    async (hours) => {
      const real = createSelectionRealService(unavailable)
      const dto = saved()
      dto.schedule = { ...dto.schedule, kind: 'hourly', interval_hours: hours }
      const view = mapSelectionStrategy(dto)
      expect(view.hourlyInterval).toBe(hours)
      vi.mocked(httpClient.put).mockResolvedValueOnce({ data: dto })
      const reread = await real.saveStrategy(view, view.id, view.version, tree)
      expect(reread.hourlyInterval).toBe(hours)
      expect(vi.mocked(httpClient.put).mock.calls[0]?.[1]).toMatchObject({
        schedule: { kind: 'hourly', interval_hours: hours },
      })
      expect(httpClient.post).not.toHaveBeenCalled()
      expect(reread.nextRunAt).toBeNull() // Non-DDL preparation does not enable schedules.
      expect(reread.scheduleAvailable).toBe(false)
    },
  )
  it('defaults legacy saved hourly JSON to one, not a new fabricated next time', () => {
    expect(mapSelectionStrategy(saved()).hourlyInterval).toBe(1)
  })
  it.each(['7d', '1d', '30d'] as const)(
    'saves, reopens and submits %s in a non-default wrapper scope',
    async (period) => {
      const service = createSelectionRealService(unavailable)
      vi.mocked(httpClient.get).mockResolvedValueOnce({
        data: {
          shop_id: 'shop-a',
          industry_id: '7',
          nodes: [
            {
              category_id: '7',
              name: '默认行业',
              children: [
                { category_id: '7001', name: '默认类目', children: [] },
              ],
            },
            {
              category_id: '41',
              name: '合成其它行业',
              children: [{ category_id: '4101', name: '父类目', children: [] }],
            },
          ],
        },
      })
      const nodes = await service.categories('shop-a')
      const dto = saved()
      dto.conditions.request.period = period
      dto.conditions.request.industry_id = '41'
      dto.conditions.request.category_ids = ['4101']
      const view = mapSelectionStrategy(dto)
      vi.mocked(httpClient.put).mockResolvedValueOnce({
        data: { ...dto, version: 4 },
      })
      const savedView = await service.saveStrategy(
        view,
        view.id,
        view.version,
        nodes,
      )
      expect(httpClient.put).toHaveBeenCalledWith(
        '/api/v1/product-selection/strategies/strategy-a',
        expect.objectContaining({
          expected_version: 3,
          conditions: {
            version: 1,
            request: expect.objectContaining({
              industry_id: '41',
              category_ids: ['4101'],
            }),
          },
        }),
      )
      expect(savedView.channels.shortVideo.conditions.categoryId).toBe(
        '41/4101',
      )
      vi.mocked(httpClient.post).mockResolvedValueOnce({
        data: { receipt_id: 'scope-run', reused: false },
      })
      await service.manual!.submit(savedView, 'scope-key', nodes, {
        id: savedView.id,
        version: savedView.version!,
      })
      expect(httpClient.post).toHaveBeenCalledWith(
        '/api/v1/product-selection/runs',
        expect.objectContaining({
          period,
          industry_id: '41',
          category_ids: ['4101'],
          strategy_id: 'strategy-a',
          strategy_version: 4,
        }),
      )
      expect(httpClient.get).toHaveBeenCalledOnce()
    },
  )
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
