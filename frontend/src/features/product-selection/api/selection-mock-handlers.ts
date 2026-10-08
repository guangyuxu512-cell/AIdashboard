import { SHOP_LIST_FIXTURE } from '@/entities/shop/fixtures/shop-list.fixture'
import { compareCandidates, validateStrategy } from '../model/selection-rules'
import {
  emptyStrategy,
  CREATOR_DEMO_OPTIONS,
  type SelectionCandidate,
  type SelectionStrategy,
  type SelectionService,
  type BatchCollectReceipt,
  type BatchCollectItemResult,
} from '../model/contracts'

// Local photographs are test fixtures; they are removed from the Real build.
const photographs = Object.values(
  import.meta.glob('../fixtures/photos/*.webp', {
    eager: true,
    query: '?url',
    import: 'default',
  }),
) as string[]

// Explicit mock mode only; in-memory handlers are not platform/Backend responses.
export function createSelectionMockHandlers(
  candidateFixture?: SelectionCandidate[],
): SelectionService {
  const shops = SHOP_LIST_FIXTURE.filter((shop) => shop.enabled)
  let sequence = 0
  const strategies: SelectionStrategy[] = [
    {
      ...emptyStrategy(),
      id: 'strategy-demo-1',
      name: '短视频热销观察',
      shopId: shops[0]!.shopId,
      shopName: shops[0]!.shopName,
      creatorId: 'creator-demo-a',
      creatorName: '演示达人 A',
      latestResult: null,
    },
    {
      ...emptyStrategy(),
      id: 'strategy-demo-2',
      name: '巨量百应观察',
      channels: {
        shortVideo: { ...emptyStrategy().channels.shortVideo, selected: false },
        baiying: { selected: true, conditions: {} },
      },
      shopId: shops[1]!.shopId,
      shopName: shops[1]!.shopName,
      creatorId: 'creator-demo-b',
      creatorName: '演示达人 B',
      latestResult: null,
    },
  ]
  const defaultCandidates: SelectionCandidate[] = Array.from(
    { length: 32 },
    (_, index) => {
      const shop = shops[index % shops.length]!
      return {
        id: `candidate-${String(index).padStart(3, '0')}`,
        shopId: shop.shopId,
        shopName: shop.shopName,
        imageUrl: photographs[index % photographs.length]!,
        title:
          index === 0
            ? 'Essence 纤长卷翘防水睫毛膏 浓密自然不晕染持久眼妆便携装'
            : `演示商品 ${index + 1}`,
        productId: `9087654321098765${String(index).padStart(3, '0')}`,
        category: index % 2 ? '生活用品 / 家居 / 收纳' : '服饰 / 女装 / 上衣',
        priceBand: index === 4 ? null : '10–50',
        listedAt:
          index % 7 === 0
            ? null
            : `2026-09-${String(1 + (index % 28)).padStart(2, '0')}T08:00:00+08:00`,
        negativeReviewRate:
          index % 8 === 0 ? null : index % 5 === 0 ? 0 : (index % 10) / 100,
        blocked: false,
        source: '短视频榜单（演示）',
        statisticalPeriod: '近7天（演示）',
        rank: index + 1,
        firstListed: index % 3 === 0,
        userPaidAmountRange: index % 6 === 0 ? null : '1万–5万',
        userPaidAmountUnit: null,
        clicksRange: '1000–5000',
        soldUnitsRange: '100–500',
        videoCountRange: '10–50',
      }
    },
  )
  const candidates = candidateFixture
    ? structuredClone(candidateFixture)
    : defaultCandidates
  function findCandidate(id: string) {
    const row = candidates.find((row) => row.id === id)
    if (!row) throw new Error('演示候选不存在')
    return row
  }
  function collect(id: string): BatchCollectItemResult {
    const row = findCandidate(id)
    return {
      candidateId: row.id,
      productId: row.productId,
      state: 'demo',
      message: '采集入库流程演示；未写入正式商品库',
    }
  }
  function validate(
    input: Parameters<SelectionService['retrieve']>[0],
    saving: boolean,
  ) {
    const errors = validateStrategy(input, saving)
    if (Object.keys(errors).length) throw new Error(Object.values(errors)[0])
    if (
      !shops.some((shop) => shop.shopId === input.shopId) ||
      !CREATOR_DEMO_OPTIONS.some((option) => option.value === input.creatorId)
    )
      throw new Error('请选择有效的演示店铺和达人账号')
  }
  return {
    available: true,
    async categories(shopId) {
      if (!shops.some((shop) => shop.shopId === shopId))
        throw new Error('店铺类目加载失败')
      return [
        {
          id: `${shopId}/clothing`,
          name: '服饰',
          children: [
            {
              id: `${shopId}/women`,
              name: '女装',
              children: [
                { id: `${shopId}/tops`, name: '上衣' },
                { id: `${shopId}/dresses`, name: '连衣裙' },
              ],
            },
          ],
        },
        {
          id: `${shopId}/home`,
          name: '生活用品',
          children: [{ id: `${shopId}/storage`, name: '家居收纳' }],
        },
      ]
    },
    async strategies() {
      return structuredClone(strategies)
    },
    async saveStrategy(input, id) {
      validate(input, true)
      const shop = shops.find((shop) => shop.shopId === input.shopId)
      const creator = CREATOR_DEMO_OPTIONS.find(
        (option) => option.value === input.creatorId,
      )
      if (!shop || !creator) throw new Error('请选择有效的演示店铺和达人账号')
      const old = strategies.find((row) => row.id === id)
      if (id && !old) throw new Error('演示策略不存在')
      const row: SelectionStrategy = {
        ...structuredClone(input),
        id: id ?? `strategy-new-${++sequence}`,
        shopName: shop.shopName,
        creatorName: creator.label,
        latestResult: old?.latestResult ?? null,
      }
      if (old) strategies.splice(strategies.indexOf(old), 1, row)
      else strategies.unshift(row)
      return structuredClone(row)
    },
    async retrieve(input, strategyId) {
      validate(input, false)
      if (!input.channels.shortVideo.selected)
        throw new Error('巨量百应获取尚未接入')
      const strategy = strategyId
        ? strategies.find((row) => row.id === strategyId)
        : null
      if (strategyId && !strategy) throw new Error('演示策略不存在')
      // Fixture count only, not a claimed implementation of platform matching.
      const count = candidates.filter(
        (row) => row.shopId === input.shopId && !row.blocked,
      ).length
      const baiyingSelected = input.channels.baiying.selected
      if (strategy)
        strategy.latestResult = `演示获取 ${count} 项${baiyingSelected ? ' · 百应未接入' : ''}`
      return {
        mode: 'mock',
        count,
        channels: [
          { channel: 'short-video', state: 'demo', count },
          ...(baiyingSelected
            ? [
                {
                  channel: 'baiying' as const,
                  state: 'unavailable' as const,
                  count: null,
                },
              ]
            : []),
        ],
        message: `演示获取完成；未向平台请求，未启动采集任务${baiyingSelected ? '；巨量百应获取尚未接入' : ''}`,
      }
    },
    async candidates(query) {
      const keyword = query.keyword.trim().toLocaleLowerCase()
      const rows = candidates.filter(
        (row) =>
          row.blocked === query.blocked &&
          (!query.shopId || row.shopId === query.shopId) &&
          (!keyword ||
            `${row.title} ${row.productId}`
              .toLocaleLowerCase()
              .includes(keyword)),
      )
      if (query.sortField && query.sortOrder)
        rows.sort((a, b) =>
          compareCandidates(
            a,
            b,
            query.sortField!,
            query.sortOrder as 'ascend' | 'descend',
          ),
        )
      const page = Math.min(
        query.page,
        Math.max(1, Math.ceil(rows.length / query.pageSize)),
      )
      return {
        items: structuredClone(
          rows.slice((page - 1) * query.pageSize, page * query.pageSize),
        ),
        total: rows.length,
        page,
        pageSize: query.pageSize,
      }
    },
    async candidate(id) {
      return structuredClone(findCandidate(id))
    },
    async demoAction(id, action) {
      const row = findCandidate(id)
      if (action === 'collect')
        return { mode: 'mock', count: 1, message: collect(id).message }
      row.blocked = action === 'block'
      return {
        mode: 'mock',
        count: 1,
        message: action === 'block' ? '已在演示列表屏蔽' : '已恢复演示候选',
      }
    },
    async collectBatch(candidateIds) {
      const results: BatchCollectReceipt['results'] = []
      const products = new Map<string, BatchCollectReceipt['results'][number]>()
      for (const id of new Set(candidateIds)) {
        let productId: string | null = null
        try {
          const row = findCandidate(id)
          productId = row.productId
          const previous = products.get(row.productId)
          if (previous) {
            previous.candidateIds.push(id)
            continue
          }
          const result = { ...collect(id), candidateIds: [id] }
          products.set(row.productId, result)
          results.push(result)
        } catch (error) {
          const failure: BatchCollectReceipt['results'][number] = {
            candidateId: id,
            candidateIds: [id],
            productId,
            state: 'failed',
            message: error instanceof Error ? error.message : '演示采集失败',
          }
          results.push(failure)
          if (productId !== null) products.set(productId, failure)
        }
      }
      return { mode: 'mock', results }
    },
  }
}
