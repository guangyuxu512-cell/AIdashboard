import { SHOP_LIST_FIXTURE } from '@/entities/shop/fixtures/shop-list.fixture'
import { compareCandidates, validateStrategy } from '../model/selection-rules'
import {
  emptyStrategy,
  CREATOR_DEMO_OPTIONS,
  type SelectionCandidate,
  type SelectionStrategy,
  type SelectionService,
} from '../model/contracts'

// Explicit mock mode only; in-memory handlers are not platform/Backend responses.
export function createSelectionMockHandlers(): SelectionService {
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
      channel: 'baiying',
      shopId: shops[1]!.shopId,
      shopName: shops[1]!.shopName,
      creatorId: 'creator-demo-b',
      creatorName: '演示达人 B',
      latestResult: null,
    },
  ]
  const candidates: SelectionCandidate[] = Array.from(
    { length: 32 },
    (_, index) => {
      const shop = shops[index % shops.length]!
      return {
        id: `candidate-${String(index).padStart(3, '0')}`,
        shopId: shop.shopId,
        shopName: shop.shopName,
        imageUrl:
          index === 2
            ? 'https://selection-image.invalid/missing.jpg'
            : 'data:image/svg+xml,' +
              encodeURIComponent(
                `<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80"><rect width="80" height="80" fill="white"/><text x="8" y="45" font-size="18">商品${index + 1}</text></svg>`,
              ),
        title:
          index === 0
            ? '超长演示商品标题：家居收纳生活用品多规格组合装（仅用于前端布局与长文本检查）'
            : `演示商品 ${index + 1}`,
        productId: `908765432109876543210${String(index).padStart(3, '0')}`,
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
  function findCandidate(id: string) {
    const row = candidates.find((row) => row.id === id)
    if (!row) throw new Error('演示候选不存在')
    return row
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
      if (input.channel === 'baiying') throw new Error('巨量百应获取尚未接入')
      const strategy = strategyId
        ? strategies.find((row) => row.id === strategyId)
        : null
      if (strategyId && !strategy) throw new Error('演示策略不存在')
      // Fixture count only, not a claimed implementation of platform matching.
      const count = candidates.filter(
        (row) => row.shopId === input.shopId && !row.blocked,
      ).length
      if (strategy) strategy.latestResult = `演示获取 ${count} 项`
      return {
        mode: 'mock',
        count,
        message: '演示获取完成；未向平台请求，未启动采集任务',
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
      if (action !== 'collect') row.blocked = action === 'block'
      return {
        mode: 'mock',
        count: 1,
        message:
          action === 'collect'
            ? '采集入库流程演示；未写入正式商品库'
            : action === 'block'
              ? '已在演示列表屏蔽'
              : '已恢复演示候选',
      }
    },
  }
}
