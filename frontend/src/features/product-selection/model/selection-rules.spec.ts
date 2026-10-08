import { describe, expect, it, vi } from 'vitest'
import { emptyStrategy, type ShortVideoConditions } from './contracts'
import { categoryOptions, validateStrategy } from './selection-rules'
import { createSelectionMockHandlers } from '../api/selection-mock-handlers'
import {
  createSelectionService,
  SELECTION_UNAVAILABLE,
} from '../api/selection-service'

const input = (conditions: Partial<ShortVideoConditions> = {}) => ({
  ...emptyStrategy(),
  channels: {
    shortVideo: {
      selected: true,
      conditions: {
        ...emptyStrategy().channels.shortVideo.conditions,
        ...conditions,
      },
    },
    baiying: { selected: false, conditions: {} },
  },
  shopId: 'shop-fixture-001',
  creatorId: 'creator-demo-a',
})
const query = () =>
  ({
    page: 1,
    pageSize: 10,
    shopId: null,
    keyword: '',
    blocked: false,
    sortField: null,
    sortOrder: false,
  }) as const

describe('selection draft and isolated mock handlers', () => {
  it('allows retrieval without saving/name/schedule; saving requires name', async () => {
    expect(validateStrategy(input(), false)).toEqual({})
    expect(validateStrategy(input(), true)).toEqual({ name: '请输入策略名称' })
    const source = createSelectionMockHandlers()
    expect((await source.retrieve(input())).mode).toBe('mock')
    expect(await source.strategies()).toHaveLength(2)
    const strategy = (await source.strategies())[0]!
    expect((await source.retrieve(strategy, strategy.id)).count).toBe(4)
    expect((await source.strategies())[0]?.latestResult).toBe('演示获取 4 项')
    await expect(source.retrieve(emptyStrategy())).rejects.toThrow(
      '请选择请求店铺',
    )
    expect(
      (await createSelectionMockHandlers().strategies())[0]?.latestResult,
    ).toBeNull()
  })
  it('validates boundaries, preserves zero price and rejects missing/inverted prices/ranks/time', () => {
    expect(
      validateStrategy(input({ priceMode: 'custom', priceAbove: 0 }), false),
    ).toEqual({})
    expect(
      validateStrategy(input({ priceMode: 'custom' }), false),
    ).toHaveProperty('channels.shortVideo.conditions.priceAbove')
    expect(
      validateStrategy(
        input({ priceMode: 'custom', priceAbove: 10, priceBelow: 5 }),
        false,
      ),
    ).toHaveProperty('channels.shortVideo.conditions.priceBelow')
    expect(
      validateStrategy(input({ rankFrom: 3, rankTo: 2 }), false),
    ).toHaveProperty('channels.shortVideo.conditions.rankTo')
    expect(
      validateStrategy(
        {
          ...input(),
          scheduled: true,
          scheduleKind: 'daily',
          dailyTime: '25:00',
        },
        false,
      ),
    ).toHaveProperty('dailyTime')
  })
  it('offers parent-all at each level without invented date options', async () => {
    const nodes =
      await createSelectionMockHandlers().categories('shop-fixture-001')
    const options = categoryOptions(nodes)
    expect(options[0]?.children?.[0]).toEqual({
      value: 'shop-fixture-001/clothing/*',
      label: '全部',
    })
    expect(options[0]?.children?.[1]?.children?.[0]?.label).toBe('全部')
  })
  it('saves and rereads independent strategy copies, preserving optional daily schedule without dispatch', async () => {
    const source = createSelectionMockHandlers()
    const first = await source.saveStrategy({
      ...input(),
      name: 'A',
      scheduled: true,
      scheduleKind: 'daily',
      dailyTime: '10:00',
    })
    await source.saveStrategy({
      ...input({ priceMode: 'custom', priceAbove: 0 }),
      name: 'B',
    })
    first.name = 'outside mutation'
    const rows = await source.strategies()
    expect(
      rows.find((row) => row.name === 'A')?.channels.shortVideo.conditions
        .priceAbove,
    ).toBeNull()
    expect(
      rows.find((row) => row.name === 'B')?.channels.shortVideo.conditions
        .priceAbove,
    ).toBe(0)
    expect(rows.find((row) => row.name === 'A')?.dailyTime).toBe('10:00')
  })
  it.each(['listedAt', 'negativeReviewRate'] as const)(
    'sorts complete matches before pagination, null last in both directions: %s',
    async (field) => {
      const source = createSelectionMockHandlers()
      const all = (await source.candidates({ ...query(), pageSize: 100 })).items
      for (const order of ['ascend', 'descend'] as const) {
        const sorted = (
          await source.candidates({
            ...query(),
            pageSize: 100,
            sortField: field,
            sortOrder: order,
          })
        ).items
        const firstPage = await source.candidates({
          ...query(),
          sortField: field,
          sortOrder: order,
        })
        expect(firstPage.items.map((row) => row.id)).toEqual(
          sorted.slice(0, 10).map((row) => row.id),
        )
        const values = sorted.map((row) =>
          field === 'listedAt'
            ? row.listedAt
              ? Date.parse(row.listedAt)
              : null
            : row.negativeReviewRate,
        )
        const valid = values.filter((value): value is number => value !== null)
        expect(
          values.slice(valid.length).every((value) => value === null),
        ).toBe(true)
        expect(valid).toEqual(
          [...valid].sort((a, b) => (order === 'ascend' ? a - b : b - a)),
        )
        for (let i = 1; i < sorted.length; i++) {
          if (values[i] === values[i - 1])
            expect(sorted[i]!.id > sorted[i - 1]!.id).toBe(true)
        }
      }
      expect(
        (await source.candidates(query())).items.map((row) => row.id),
      ).toEqual(all.slice(0, 10).map((row) => row.id))
      expect(all.some((row) => row.negativeReviewRate === 0)).toBe(true)
      expect(
        all.every(
          (row) =>
            typeof row.productId === 'string' && row.productId.length === 19,
        ),
      ).toBe(true)
    },
  )
  it('filters across all pages and block/restore only changes the mock pool', async () => {
    const source = createSelectionMockHandlers()
    const first = (await source.candidates(query())).items[0]!
    expect(
      (await source.candidates({ ...query(), keyword: first.productId })).total,
    ).toBe(1)
    await source.demoAction(first.id, 'block')
    expect((await source.candidates(query())).total).toBe(31)
    expect(
      (await source.candidates({ ...query(), blocked: true })).items[0]?.id,
    ).toBe(first.id)
    await source.demoAction(first.id, 'restore')
    expect((await source.candidates(query())).total).toBe(32)
    expect((await source.demoAction(first.id, 'collect')).message).toContain(
      '未写入正式商品库',
    )
    expect((await source.candidate(first.id)).userPaidAmountUnit).toBeNull()
  })
  it('does not fake Baiying results, unsupported category data or real endpoints', async () => {
    const mock = createSelectionMockHandlers()
    await expect(
      mock.retrieve({
        ...input(),
        channels: {
          shortVideo: { ...input().channels.shortVideo, selected: false },
          baiying: { selected: true, conditions: {} },
        },
      }),
    ).rejects.toThrow('尚未接入')
    await expect(mock.categories('missing')).rejects.toThrow('类目加载失败')
    const real = await createSelectionService('real')
    expect(real.available).toBe(false)
    await expect(real.previewPeriod('7d')).rejects.toThrow(
      SELECTION_UNAVAILABLE,
    )
    await expect(real.candidates(query())).rejects.toThrow(
      SELECTION_UNAVAILABLE,
    )
    await expect(real.retrieve(input())).rejects.toThrow(SELECTION_UNAVAILABLE)
    expect((await createSelectionService('mock')).available).toBe(true)
    vi.stubEnv('VITE_API_MODE', 'real')
    try {
      expect((await createSelectionService('mock')).available).toBe(false)
    } finally {
      vi.unstubAllEnvs()
    }
  })
  it.each(['realtime', '1d', '7d', '30d'] as const)(
    'supplies explicit Mock ranges but saves only the relative period: %s',
    async (period) => {
      const service = createSelectionMockHandlers()
      const preview = await service.previewPeriod(period)
      expect(preview.mode).toBe('mock')
      expect(preview.rangeLabel).toMatch(/^2026-/)
      const saved = await service.saveStrategy({
        ...input({ period }),
        name: period,
      })
      const read = (await service.strategies()).find(
        (row) => row.id === saved.id,
      )!
      expect(read.channels.shortVideo.conditions.period).toBe(period)
      expect(Object.keys(read.channels.shortVideo.conditions).sort()).toEqual(
        Object.keys(emptyStrategy().channels.shortVideo.conditions).sort(),
      )
      expect(JSON.stringify(read)).not.toContain(preview.rangeLabel)
    },
  )
  it('preserves two channel configurations independently, reports partial retrieval honestly and rejects no-channel drafts', async () => {
    const mock = createSelectionMockHandlers()
    const draft = input({
      priceMode: 'custom',
      priceAbove: 0,
      priceBelow: 50,
      rankFrom: 2,
      rankTo: 20,
    })
    draft.channels.baiying.selected = true
    const saved = await mock.saveStrategy({ ...draft, name: '多渠道' })
    const receipt = await mock.retrieve(saved, saved.id)
    expect(receipt.channels).toEqual([
      { channel: 'short-video', state: 'demo', count: 4 },
      { channel: 'baiying', state: 'unavailable', count: null },
    ])
    saved.channels.shortVideo.conditions.priceAbove = 100
    saved.channels.baiying.selected = false
    const read = (await mock.strategies()).find((row) => row.name === '多渠道')!
    expect(read.channels.shortVideo.conditions.priceAbove).toBe(0)
    expect(read.channels.baiying).toEqual({ selected: true, conditions: {} })
    read.channels.shortVideo.selected = false
    read.channels.baiying.selected = false
    expect(validateStrategy(read, false)).toHaveProperty('channels')
    expect(receipt.message).toContain('巨量百应获取尚未接入')
  })
  it('uses ten locally bundled photographs, with no broken images in normal fixtures', async () => {
    const rows = (await createSelectionMockHandlers().candidates(query())).items
    expect(rows).toHaveLength(10)
    expect(new Set(rows.map((row) => row.imageUrl)).size).toBe(10)
    expect(rows.every((row) => row.imageUrl?.includes('.webp'))).toBe(true)
    expect(
      rows.some(
        (row) =>
          row.imageUrl?.includes('invalid') || row.imageUrl?.includes('svg'),
      ),
    ).toBe(false)
  })
  it('batch demo deduplicates products and returns failures without losing other item results', async () => {
    const first = await createSelectionMockHandlers().candidate('candidate-000')
    const source = createSelectionMockHandlers([
      first,
      { ...first, id: 'alias-same-product' },
      { ...first, id: 'other-product', productId: '9087654321098765999' },
    ])
    const result = await source.collectBatch([
      first.id,
      first.id,
      'missing',
      'alias-same-product',
      'other-product',
    ])
    expect(result.mode).toBe('mock')
    expect(result.results).toHaveLength(3)
    expect(result.results[0]).toMatchObject({
      state: 'demo',
      productId: first.productId,
      candidateIds: [first.id, 'alias-same-product'],
    })
    expect(result.results[1]).toMatchObject({
      state: 'failed',
      candidateId: 'missing',
    })
    expect(result.results[2]).toMatchObject({
      state: 'demo',
      productId: '9087654321098765999',
    })
    expect(result.results[0]!.message).toBe(
      (await source.demoAction(first.id, 'collect')).message,
    )
    expect(await source.collectBatch([])).toEqual({ mode: 'mock', results: [] })
    expect(await source.candidate(first.id)).toEqual(first)
    await expect(
      (await createSelectionService('real')).collectBatch([first.id]),
    ).rejects.toThrow(SELECTION_UNAVAILABLE)
  })
})
