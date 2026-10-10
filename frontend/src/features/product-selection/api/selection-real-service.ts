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
} from './selection-read-api'

function categoryNodes(
  nodes: SelectionCategoryDto[],
  ancestors: string[] = [],
): CategoryNode[] {
  return nodes.map((node) => {
    const path = [...ancestors, node.category_id]
    return {
      // Qualified display identities keep repeated '0/全部' nodes distinct.
      // They are not a frozen category_id/industry_id platform mapping.
      id: path.join('/'),
      name: node.name,
      children: categoryNodes(node.children, path),
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
      leaderboardName: '罗盘商品榜（渠道映射待确认）',
      scopeKey: dto.source_scope_hash,
      category: source.business.category_id,
      statisticalPeriod: `${dto.period_begin}～${dto.period_end}`,
      // date_type is not interpreted as a shortcut label without evidence.
      periodLabel: '',
      rankFrom: null,
      rankTo: null,
      checkedAt: dto.checked_at,
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
  return {
    available: false,
    candidatesAvailable: true,
    latestRun: readLatestSelectionRun,
    previewPeriod: unavailable,
    async categories(shopId) {
      const tree = await readSelectionCategories(shopId)
      if (tree.shop_id !== shopId)
        throw new Error('类目响应与当前请求店铺不一致')
      return categoryNodes(tree.nodes)
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
