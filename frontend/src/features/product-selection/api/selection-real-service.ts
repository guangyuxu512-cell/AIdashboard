import type {
  CategoryNode,
  SelectionCandidate,
  SelectionService,
} from '../model/contracts'
import {
  readSelectionCandidates,
  readSelectionObservation,
  readLatestSelectionRun,
  readSelectionCategories,
  type SelectionCategoryDto,
  type SelectionObservationDto,
  type SelectionMetricDto,
  readSelectionCapabilities,
  submitSelectionRun,
} from './selection-read-api'

function categoryNodes(
  nodes: SelectionCategoryDto[],
  ancestors: string[] = [],
  industryId: string | null = null,
): CategoryNode[] {
  const industryWrapped =
    ancestors.length === 0 &&
    nodes.some((node) => node.category_id === industryId)
  return nodes
    .filter(
      (node) =>
        /^[0-9]+$/.test(node.category_id) && !/^0+$/.test(node.category_id),
    )
    .map((node) => {
      const path = [...ancestors, node.category_id]
      const nodeIndustryId =
        industryWrapped && node.category_id !== industryId ? null : industryId
      // The observed outer industry node is part of the display tree, not
      // category_id. Keep display identities intact; submit industry separately.
      const categoryPath = path[0] === nodeIndustryId ? path.slice(1) : path
      return {
        // Qualified display identities keep repeated '0/全部' nodes distinct.
        // They are not a frozen category_id/industry_id platform mapping.
        id: path.join('/'),
        name: node.name,
        children: categoryNodes(node.children, path, nodeIndustryId),
        requestScope:
          nodeIndustryId && categoryPath.length
            ? { industryId: nodeIndustryId, categoryIds: categoryPath }
            : undefined,
      }
    })
}

function range(metric: SelectionMetricDto): string | null {
  if (metric.state !== 'available' || !metric.value_range) return null
  // No scaling, rounding, approximate midpoint or invented suffix.
  return metric.value_range.map((item) => item.value).join('–')
}

export function mapSelectionObservation(
  dto: SelectionObservationDto,
): SelectionCandidate {
  const source = dto.source_context
  const merchant = dto.merchants.length === 1 ? dto.merchants[0]! : null
  const leaderboardId = `${source.platform}:${source.endpoint}`
  return {
    id: dto.observation_id,
    productId: dto.product_id,
    title: dto.title ?? '—',
    shopId: dto.request_shop_id,
    shopName: dto.request_shop_name,
    merchant: merchant
      ? {
          shopId: merchant.platform_shop_id,
          name: merchant.name ?? '—',
          competitor: false,
        }
      : null,
    imageUrl: dto.image_url,
    sourceUrl: dto.source_url,
    category: dto.category_path?.join(' / ') ?? '—',
    priceBand: dto.price_band,
    listedAt: dto.first_on_shelf_date,
    negativeReviewRate: null,
    negativeReviewRateRaw:
      dto.bad_comment_rate_raw === null
        ? null
        : { value: dto.bad_comment_rate_raw, unit: dto.bad_comment_rate_unit },
    basicInfoError: dto.last_error_stage?.startsWith('basic_info')
      ? (dto.last_error_code ?? '商品补充信息未完成')
      : null,
    blocked: false,
    source: '罗盘商品榜',
    sourceContext: {
      leaderboardId,
      leaderboardName: source.date_selection
        ? '罗盘短视频商品榜'
        : '罗盘商品榜（渠道映射待确认）',
      scopeKey: dto.source_scope_hash,
      category: source.business.category_id,
      statisticalPeriod: `${dto.period_begin}～${dto.period_end}`,
      // date_type is not interpreted as a shortcut label without evidence.
      periodLabel: source.date_selection ? '近7天' : '',
      rankFrom: source.date_selection?.rank_from ?? null,
      rankTo: source.date_selection?.rank_to ?? null,
      checkedAt: dto.checked_at,
      dateFallback: source.date_selection?.actual_window === 'backup',
    },
    rank: dto.rank,
    previousRank:
      dto.previous_rank === null
        ? null
        : {
            rank: dto.previous_rank,
            leaderboardId,
            scopeKey: dto.source_scope_hash,
            checkedAt: dto.previous_checked_at,
          },
    discovery: 'unknown',
    firstDiscoveredAt: dto.first_seen_at,
    metricsRetrievedAt: dto.metrics_retrieved_at,
    collectionStatus: 'unknown',
    firstListed: dto.newly_on_ranking,
    userPaidAmountRange: range(dto.video_metric_ranges.pay_amt),
    userPaidAmountUnit: null,
    clicksRange: range(dto.video_metric_ranges.product_click_cnt),
    soldUnitsRange: range(dto.video_metric_ranges.pay_combo_cnt),
    videoCountRange: range(dto.video_metric_ranges.video_cnt),
  }
}

export function createSelectionRealService(
  unavailable: () => Promise<never>,
): SelectionService {
  const shopCategories = new Map<string, CategoryNode[]>()
  function findScope(
    nodes: CategoryNode[],
    id: string,
  ): CategoryNode['requestScope'] {
    for (const node of nodes) {
      if (node.id === id) return node.requestScope
      const result = findScope(node.children ?? [], id)
      if (result) return result
    }
  }
  return {
    available: false,
    candidatesAvailable: true,
    latestRun: readLatestSelectionRun,
    manual: {
      capabilities: readSelectionCapabilities,
      async submit(input, submissionKey) {
        const choice = input.channels.shortVideo.conditions
        // A Query cache can outlive this service instance. Re-establish its
        // actual tree rather than guessing an industry from a display ID.
        if (input.shopId && !shopCategories.has(input.shopId)) {
          const tree = await readSelectionCategories(input.shopId)
          if (tree.shop_id !== input.shopId)
            throw new Error('类目响应与当前请求店铺不一致')
          shopCategories.set(
            input.shopId,
            categoryNodes(tree.nodes, [], tree.industry_id),
          )
        }
        const scope =
          input.shopId && choice.categoryId
            ? findScope(
                shopCategories.get(input.shopId) ?? [],
                choice.categoryId,
              )
            : undefined
        if (!input.shopId || !scope)
          throw new Error('请选择当前店铺已加载的真实类目')
        if (
          !input.channels.shortVideo.selected ||
          input.channels.baiying.selected ||
          choice.period !== '7d' ||
          choice.brand !== 'all' ||
          choice.priceMode !== 'all' ||
          choice.firstListedOnly ||
          input.scheduled ||
          choice.priceAbove !== null ||
          choice.priceBelow !== null
        )
          throw new Error('当前仅支持短视频近7天、不限品牌与价格的手动获取')
        if (
          choice.rankFrom === null ||
          choice.rankTo === null ||
          !Number.isInteger(choice.rankFrom) ||
          !Number.isInteger(choice.rankTo) ||
          choice.rankFrom < 1 ||
          choice.rankTo > 20 ||
          choice.rankFrom > choice.rankTo
        )
          throw new Error('当前支持第1–20名，请填写完整排名范围')
        return submitSelectionRun({
          submission_key: submissionKey,
          shop_id: input.shopId,
          channel: 'short-video',
          period: '7d',
          industry_id: scope.industryId,
          category_ids: scope.categoryIds,
          brand: 'all',
          price_mode: 'all',
          first_listed_only: false,
          rank_from: choice.rankFrom,
          rank_to: choice.rankTo,
        })
      },
    },
    previewPeriod: unavailable,
    async categories(shopId) {
      const tree = await readSelectionCategories(shopId)
      if (tree.shop_id !== shopId)
        throw new Error('类目响应与当前请求店铺不一致')
      const nodes = categoryNodes(tree.nodes, [], tree.industry_id)
      shopCategories.set(shopId, nodes)
      return nodes
    },
    strategies: unavailable,
    saveStrategy: unavailable,
    retrieve: unavailable,
    async candidates(query) {
      if (query.blocked || query.sortField === 'negativeReviewRate')
        return unavailable()
      const page = await readSelectionCandidates({
        page: query.page,
        pageSize: query.pageSize,
        shopId: query.shopId,
        search: query.keyword,
        sortField:
          query.sortField === 'listedAt' ? 'first_on_shelf_date' : 'checked_at',
        sortDirection:
          query.sortField && query.sortOrder === 'ascend' ? 'asc' : 'desc',
      })
      return {
        items: page.items.map(mapSelectionObservation),
        total: page.total,
        page: page.page,
        pageSize: page.page_size,
      }
    },
    async candidate(id) {
      return mapSelectionObservation(await readSelectionObservation(id))
    },
    demoAction: unavailable,
    collectBatch: unavailable,
    updateCompassMetrics: unavailable,
    markCompetitor: unavailable,
  }
}
