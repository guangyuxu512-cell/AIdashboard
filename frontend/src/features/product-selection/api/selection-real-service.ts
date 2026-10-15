import type {
  CategoryNode,
  SelectionCandidate,
  SelectionService,
  SelectionStrategy,
  StrategyInput,
  CategoryNode as Category,
} from '../model/contracts'
import {
  readSelectionCandidates,
  readSelectionObservation,
  readLatestSelectionRun,
  readSelectionRun,
  readSelectionCategories,
  type SelectionCategoryDto,
  type SelectionObservationDto,
  type SelectionMetricDto,
  readSelectionCapabilities,
  submitSelectionRun,
  readSelectionBatches,
  blockSelectionCandidate,
  submitSelectionBasic,
  readSelectionBasic,
} from './selection-read-api'
import { formatSelectionInterval } from '../model/metric-display'
import { runResult, triggerFailure } from '../model/run-display'
import { realPriceErrors } from '../model/selection-rules'
import { basicFailure, basicStatus } from '../model/basic-display'
import {
  readStrategies,
  readSavedStrategy,
  writeStrategy,
  toggleSavedStrategy,
  type SelectionRelativeDto,
  type SelectionStrategyDto,
} from './selection-strategy-api'

export function mapSelectionStrategy(
  dto: SelectionStrategyDto,
): SelectionStrategy {
  const request = dto.conditions.request
  return {
    id: dto.strategy_id,
    version: dto.version,
    name: dto.name,
    shopId: dto.shop_id,
    shopName: dto.shop_name,
    creatorId: null,
    creatorName: '—',
    channels: {
      shortVideo: {
        selected: request.channel === 'short-video',
        conditions: {
          categoryId: [request.industry_id, ...request.category_ids].join('/'),
          period: request.period,
          brand: request.brand,
          priceMode: request.price_mode,
          priceAbove:
            request.price_above === null ? null : Number(request.price_above),
          priceBelow:
            request.price_below === null ? null : Number(request.price_below),
          firstListedOnly: request.first_listed_only,
          rankFrom: request.rank_from,
          rankTo: request.rank_to,
        },
      },
      baiying: { selected: false, conditions: {} },
    },
    scheduled: dto.schedule.scheduled,
    scheduleKind: dto.schedule.kind,
    hourlyInterval: dto.schedule.interval_hours ?? 1,
    dailyTime: dto.schedule.daily_time,
    enabled: dto.enabled,
    latestResult:
      dto.latest_trigger?.trigger_result === 'blocked'
        ? triggerFailure(
            dto.latest_trigger.error_code,
            dto.latest_trigger.error_stage,
          )
        : dto.latest_run
          ? runResult(dto.latest_run)
          : null,
    latestExecution: dto.latest_run,
    latestReceiptId:
      dto.latest_receipt_id ?? dto.latest_trigger?.receipt_id ?? null,
    scheduleAvailable: dto.schedule_available,
    scheduleExecutionEnabled: dto.schedule_execution_enabled ?? false,
    latestTrigger: dto.latest_trigger ?? null,
    nextRunAt: dto.next_run_at,
    requestScope: {
      industryId: request.industry_id,
      categoryIds: request.category_ids,
    },
  }
}

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
      // Every returned wrapper root supplies its own industry_id. The scalar
      // is only the shop's default; it must not disable the other actual roots.
      const nodeIndustryId = industryWrapped ? node.category_id : industryId
      // Keep the root in display identities, but outside category_id. Root-all
      // has no confirmed category expression and still has no requestScope.
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

function range(
  metric: SelectionMetricDto,
  kind: 'count' | 'amount' = 'count',
): string | null {
  if (metric.state !== 'available' || !metric.value_range) return null
  return formatSelectionInterval(metric.value_range, kind)
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
    negativeReviewRate:
      dto.bad_comment_rate_unit === 4 &&
      dto.bad_comment_rate_raw !== null &&
      dto.bad_comment_rate_raw.trim() !== '' &&
      Number.isFinite(Number(dto.bad_comment_rate_raw)) &&
      Number(dto.bad_comment_rate_raw) >= 0 &&
      Number(dto.bad_comment_rate_raw) <= 1
        ? Number(dto.bad_comment_rate_raw)
        : null,
    negativeReviewRateRaw:
      dto.bad_comment_rate_raw === null
        ? null
        : { value: dto.bad_comment_rate_raw, unit: dto.bad_comment_rate_unit },
    basicInfoStatus: dto.basic_info_status ?? null,
    resultRunId: dto.result_run_id ?? null,
    basicInfoError:
      dto.basic_info_status && dto.basic_info_status.state !== 'succeeded'
        ? basicStatus(dto.basic_info_status)
        : dto.last_error_stage?.startsWith('basic_info')
          ? basicFailure(dto.last_error_code, dto.last_error_stage)
          : null,
    blocked: dto.blocked ?? false,
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
      periodLabel: source.date_selection
        ? {
            shanghai_7d_once: '近7天',
            shanghai_realtime_today: '实时',
            shanghai_1d_yesterday: '近1天',
            shanghai_30d_complete_days: '近30天',
          }[source.date_selection.policy]
        : '',
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
    discovery:
      dto.discovery_state === 'new'
        ? 'new-in-scope'
        : (dto.discovery_state ?? 'unknown'),
    firstDiscoveredAt: dto.first_seen_at,
    metricsRetrievedAt: dto.metrics_retrieved_at,
    collectionStatus: 'unknown',
    firstListed: dto.newly_on_ranking,
    userPaidAmountRange: range(dto.video_metric_ranges.pay_amt, 'amount'),
    userPaidAmountUnit: null,
    clicksRange: range(dto.video_metric_ranges.product_click_cnt),
    soldUnitsRange: range(dto.video_metric_ranges.pay_combo_cnt),
    videoCountRange: range(dto.video_metric_ranges.video_cnt),
  }
}

export function createSelectionRealService(
  unavailable: () => Promise<never>,
): SelectionService {
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
  async function relativeInput(
    input: StrategyInput,
    categories?: Category[],
  ): Promise<SelectionRelativeDto> {
    if (!input.shopId) throw new Error('请选择已授权的请求店铺')
    const choice = input.channels.shortVideo.conditions
    if (!categories) {
      const tree = await readSelectionCategories(input.shopId)
      if (tree.shop_id !== input.shopId)
        throw new Error('类目响应与当前请求店铺不一致')
      categories = categoryNodes(tree.nodes, [], tree.industry_id)
    }
    let scope = choice.categoryId
      ? findScope(categories, choice.categoryId)
      : undefined
    // Saved scopes are normalized platform IDs; the loaded tree may or may
    // not contain an industry display wrapper. Resolve its exact path instead
    // of guessing a display ID. Only a saved, unedited path gets this mapping.
    const saved =
      'requestScope' in input
        ? (input as SelectionStrategy).requestScope
        : undefined
    if (
      !scope &&
      saved &&
      choice.categoryId === [saved.industryId, ...saved.categoryIds].join('/')
    ) {
      function match(nodes: Category[]): Category['requestScope'] {
        for (const node of nodes) {
          if (
            node.requestScope?.industryId === saved!.industryId &&
            JSON.stringify(node.requestScope.categoryIds) ===
              JSON.stringify(saved!.categoryIds)
          )
            return node.requestScope
          const found = match(node.children ?? [])
          if (found) return found
        }
      }
      scope = match(categories)
    }
    if (!scope) throw new Error('请选择当前店铺已加载的真实类目')
    if (
      !input.channels.shortVideo.selected ||
      input.channels.baiying.selected ||
      !['realtime', '1d', '7d', '30d'].includes(choice.period) ||
      !['all', 'known', 'unknown'].includes(choice.brand)
    )
      throw new Error('未确认的渠道、日期、品牌或价格条件暂不可执行')
    const priceErrors = realPriceErrors(choice)
    if (Object.keys(priceErrors).length)
      throw new Error(Object.values(priceErrors)[0])
    if (
      choice.rankFrom === null ||
      choice.rankTo === null ||
      !Number.isInteger(choice.rankFrom) ||
      !Number.isInteger(choice.rankTo) ||
      choice.rankFrom < 1 ||
      choice.rankTo > 200 ||
      choice.rankFrom > choice.rankTo
    )
      throw new Error('请填写第1–200名以内的完整排名范围')
    return {
      channel: 'short-video',
      period: choice.period,
      industry_id: scope.industryId,
      category_ids: scope.categoryIds,
      brand: choice.brand,
      price_mode: choice.priceMode,
      price_above:
        choice.priceMode === 'custom' ? String(choice.priceAbove) : null,
      price_below:
        choice.priceMode === 'custom' ? String(choice.priceBelow) : null,
      first_listed_only: choice.firstListedOnly,
      rank_from: choice.rankFrom,
      rank_to: choice.rankTo,
    }
  }
  return {
    available: false,
    strategySaveAvailable: true,
    scheduleAvailable: true,
    candidatesAvailable: true,
    candidateBlockAvailable: true,
    batches: async (strategyId, shopId) =>
      (await readSelectionBatches(strategyId, shopId)).items,
    async blockCandidate(id, blocked) {
      await blockSelectionCandidate(id, blocked)
    },
    basic: { submit: submitSelectionBasic, latest: readSelectionBasic },
    latestRun: readLatestSelectionRun,
    run: readSelectionRun,
    manual: {
      capabilities: readSelectionCapabilities,
      async submit(input, submissionKey, categories, strategy) {
        const relative = await relativeInput(input, categories)
        return submitSelectionRun({
          ...relative,
          shop_id: input.shopId!,
          submission_key: submissionKey,
          ...(strategy
            ? { strategy_id: strategy.id, strategy_version: strategy.version }
            : {}),
        })
      },
    },
    previewPeriod: unavailable,
    async categories(shopId, options) {
      const tree = await readSelectionCategories(shopId, options)
      if (tree.shop_id !== shopId)
        throw new Error('类目响应与当前请求店铺不一致')
      return categoryNodes(tree.nodes, [], tree.industry_id)
    },
    async strategies() {
      return (
        await readStrategies({ page: 1, pageSize: 100, search: '' })
      ).items.map(mapSelectionStrategy)
    },
    async strategy(id) {
      return mapSelectionStrategy(await readSavedStrategy(id))
    },
    async strategiesPage(query) {
      const page = await readStrategies(query)
      return {
        items: page.items.map(mapSelectionStrategy),
        total: page.total,
        page: page.page,
        pageSize: page.page_size,
      }
    },
    async saveStrategy(input, id, expectedVersion, categories) {
      const relative = await relativeInput(input, categories)
      return mapSelectionStrategy(
        await writeStrategy(
          {
            name: input.name,
            shop_id: input.shopId!,
            enabled: input.enabled,
            conditions: { version: 1, request: relative },
            schedule: {
              scheduled: input.scheduled,
              kind: input.scheduleKind,
              interval_hours: input.hourlyInterval,
              daily_time: input.dailyTime,
              timezone: 'Asia/Shanghai',
            },
          },
          id,
          expectedVersion,
        ),
      )
    },
    async toggleStrategy(row, enabled) {
      if (!row.version) throw new Error('请刷新已保存的策略版本')
      return mapSelectionStrategy(
        await toggleSavedStrategy(row.id, enabled, row.version),
      )
    },
    retrieve: unavailable,
    async candidates(query) {
      if (query.sortField === 'negativeReviewRate') return unavailable()
      const page = await readSelectionCandidates({
        page: query.page,
        pageSize: query.pageSize,
        shopId: query.shopId,
        search: query.keyword,
        blocked: query.blocked,
        resultScope: query.resultScope,
        strategyId: query.strategyId,
        receiptId: query.receiptId,
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
        context: page.context,
      }
    },
    async candidate(id, receiptId) {
      return mapSelectionObservation(
        await readSelectionObservation(id, receiptId),
      )
    },
    demoAction: unavailable,
    collectBatch: unavailable,
    updateCompassMetrics: unavailable,
    markCompetitor: unavailable,
  }
}
