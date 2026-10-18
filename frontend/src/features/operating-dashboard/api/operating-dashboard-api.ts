import type { ShopPlatform } from '@/entities/shop'
import { httpClient } from '@/shared/api'

import type {
  DashboardComparison,
  OperatingDashboardDateRange,
  OperatingDashboardCoverage,
  OperatingDashboardFilters,
  OperatingDashboardRead,
  OperatingDashboardShopOption,
  OperatingDashboardSort,
  OperatingDashboardTableRow,
} from '../model/types'

const basePath = '/api/v1/operating-dashboard'

interface DateRangeDto {
  start_date: string
  end_date: string
}

interface ComparisonDto {
  state: DashboardComparison['state']
  percentage: number | null
  favorable: boolean | null
}

interface ShopOptionDto {
  shop_id: string
  shop_name: string
  platform: ShopPlatform
}

interface TableRowDto {
  shop_id: string
  shop_name: string
  platform: ShopPlatform
  turnover_cents: number | null
  order_count: number | null
  refund_order_count: number | null
  refund_order_coverage_complete: boolean
  experience_score: null
  collected_at: string | null
  coverage_complete: boolean
  not_operating_for_range: boolean
}

export interface OperatingDashboardSessionRecoveryDto {
  collection_job_id: string
  collection_item_id: string
  session_version: number
  requires_validation: boolean
}

interface DashboardReadDto {
  date_range: DateRangeDto
  comparison_date_range: DateRangeDto
  trend_date_range: DateRangeDto
  all_available_shops: ShopOptionDto[]
  summary: {
    turnover_cents: number | null
    order_count: number | null
    refund_order_count: number | null
    refund_order_coverage_complete: boolean
    shop_count: number
    turnover_comparison: ComparisonDto
    order_comparison: ComparisonDto
    refund_order_comparison: ComparisonDto
    shop_count_comparison: ComparisonDto
  }
  trend: Array<{
    business_date: string
    turnover_cents: number | null
    order_count: number | null
    coverage_complete: boolean
  }>
  table: {
    items: TableRowDto[]
    total: number
    page: number
    page_size: number
  }
  coverage: {
    state: OperatingDashboardCoverage['state']
    supported_shop_count: number
    collected_shop_days: number
    total_shop_days: number
    missing_shop_days: number
    missing_samples: Array<{
      shop_id: string
      shop_name: string
      business_date: string
      state: OperatingDashboardCoverage['missingSamples'][number]['state']
      failure_reason: string | null
      session_recovery?: OperatingDashboardSessionRecoveryDto | null
      recovery_block_reason?: string | null
    }>
    missing_samples_truncated: boolean
    manual_backfill_required: boolean
    not_operating_shop_days: number
    shops_with_unknown_operating_start: number
    no_operating_scope: boolean
  }
  collection_available: boolean
}

export interface OperatingDashboardCollectionItemDto {
  collection_item_id: string
  shop_id: string
  business_date: string
  status:
    | 'pending'
    | 'running'
    | 'succeeded'
    | 'failed'
    | 'skipped'
    | 'paused_reauthorization'
  retryable: boolean
  failure_code: string | null
  failure_message: string | null
  failure_stage: string | null
  attempt_count: number
}

export interface OperatingDashboardCollectionJobDto {
  collection_job_id: string
  status: 'pending' | 'running' | 'succeeded' | 'partial_failed' | 'failed'
  counts: {
    pending: number
    running: number
    succeeded: number
    failed: number
    skipped: number
    paused_reauthorization: number
  }
  items: OperatingDashboardCollectionItemDto[]
}

export interface OperatingDashboardCollectionSubmissionDto {
  state:
    | 'up_to_date'
    | 'collection_queued'
    | 'attention_required'
    | 'unsupported'
    | 'not_operating'
  message: string
  collection_job: OperatingDashboardCollectionJobDto | null
  missing_shop_days: number
  queued_shop_days: number
  active_shop_days: number
  blocked_shop_days: number
  // Optional during a rolling Backend/Frontend deployment. Older Backends
  // did not expose durable prior-day waiting counts.
  waiting_shop_days?: number
  refund_attention_shop_days: number
  not_operating_shop_days: number
}

export interface OperatingDashboardCollectionSubmission {
  state: OperatingDashboardCollectionSubmissionDto['state']
  message: string
  collectionJob: OperatingDashboardCollectionJobDto | null
  missingShopDays: number
  queuedShopDays: number
  activeShopDays: number
  blockedShopDays: number
  waitingShopDays: number
  refundAttentionShopDays: number
  notOperatingShopDays: number
}

export interface OperatingDashboardReadParams {
  range: OperatingDashboardDateRange
  filters: OperatingDashboardFilters
  sort: OperatingDashboardSort | null
  page: number
  pageSize: number
}

function mapDateRange(value: DateRangeDto): OperatingDashboardDateRange {
  return { startDate: value.start_date, endDate: value.end_date }
}

function mapComparison(value: ComparisonDto): DashboardComparison {
  if (value.state === 'unavailable' || value.state === 'equal') {
    return { state: value.state }
  }
  if (value.percentage === null || value.favorable === null) {
    // A partial comparison must not become a made-up 0% in the dashboard.
    return { state: 'unavailable' }
  }
  return {
    state: value.state,
    percentage: value.percentage,
    favorable: value.favorable,
  }
}

function mapShop(value: ShopOptionDto): OperatingDashboardShopOption {
  return {
    shopId: value.shop_id,
    shopName: value.shop_name,
    platform: value.platform,
  }
}

function mapTableRow(value: TableRowDto): OperatingDashboardTableRow {
  return {
    shopId: value.shop_id,
    shopName: value.shop_name,
    platform: value.platform,
    turnoverCents: value.turnover_cents,
    orderCount: value.order_count,
    refundOrderCount: value.refund_order_count,
    // Merchant experience has no verified platform contract in V1.  The
    // backend deliberately returns null rather than a guessed score object.
    experience: null,
    collectedAt: value.collected_at,
    coverageComplete: value.coverage_complete,
    refundOrderCoverageComplete: value.refund_order_coverage_complete,
    notOperatingForRange: value.not_operating_for_range,
  }
}

function mapCollectionSubmission(
  value: OperatingDashboardCollectionSubmissionDto,
): OperatingDashboardCollectionSubmission {
  return {
    state: value.state,
    message: value.message,
    collectionJob: value.collection_job,
    missingShopDays: value.missing_shop_days,
    queuedShopDays: value.queued_shop_days,
    activeShopDays: value.active_shop_days,
    blockedShopDays: value.blocked_shop_days,
    waitingShopDays: value.waiting_shop_days ?? 0,
    refundAttentionShopDays: value.refund_attention_shop_days,
    notOperatingShopDays: value.not_operating_shop_days,
  }
}

export function mapOperatingDashboardRead(
  value: DashboardReadDto,
): OperatingDashboardRead {
  const allAvailableShops = value.all_available_shops.map(mapShop)
  return {
    dateRange: mapDateRange(value.date_range),
    comparisonDateRange: mapDateRange(value.comparison_date_range),
    trendDateRange: mapDateRange(value.trend_date_range),
    allAvailableShops,
    availableShops: allAvailableShops,
    summary: {
      turnoverCents: value.summary.turnover_cents,
      orderCount: value.summary.order_count,
      refundOrderCount: value.summary.refund_order_count,
      refundOrderCoverageComplete: value.summary.refund_order_coverage_complete,
      shopCount: value.summary.shop_count,
      turnoverComparison: mapComparison(value.summary.turnover_comparison),
      orderComparison: mapComparison(value.summary.order_comparison),
      refundOrderComparison: mapComparison(
        value.summary.refund_order_comparison,
      ),
      shopCountComparison: mapComparison(value.summary.shop_count_comparison),
    },
    trend: value.trend.map((point) => ({
      businessDate: point.business_date,
      turnoverCents: point.turnover_cents,
      orderCount: point.order_count,
      coverageComplete: point.coverage_complete,
    })),
    tableRows: value.table.items.map(mapTableRow),
    tablePage: {
      total: value.table.total,
      page: value.table.page,
      pageSize: value.table.page_size,
    },
    coverage: {
      state: value.coverage.state,
      supportedShopCount: value.coverage.supported_shop_count,
      collectedShopDays: value.coverage.collected_shop_days,
      totalShopDays: value.coverage.total_shop_days,
      missingShopDays: value.coverage.missing_shop_days,
      missingSamples: value.coverage.missing_samples.map((sample) => ({
        shopId: sample.shop_id,
        shopName: sample.shop_name,
        businessDate: sample.business_date,
        state: sample.state,
        failureReason: sample.failure_reason,
        sessionRecovery: sample.session_recovery
          ? {
              collectionJobId: sample.session_recovery.collection_job_id,
              collectionItemId: sample.session_recovery.collection_item_id,
              sessionVersion: sample.session_recovery.session_version,
              requiresValidation: sample.session_recovery.requires_validation,
            }
          : null,
        recoveryBlockReason: sample.recovery_block_reason ?? null,
      })),
      missingSamplesTruncated: value.coverage.missing_samples_truncated,
      manualBackfillRequired: value.coverage.manual_backfill_required,
      notOperatingShopDays: value.coverage.not_operating_shop_days,
      shopsWithUnknownOperatingStart:
        value.coverage.shops_with_unknown_operating_start,
      noOperatingScope: value.coverage.no_operating_scope,
    },
    collectionAvailable: value.collection_available,
  }
}

function toApiSortField(
  field: OperatingDashboardSort['field'],
):
  | 'shop_name'
  | 'turnover_cents'
  | 'order_count'
  | 'refund_order_count'
  | 'collected_at' {
  const fields: Record<
    OperatingDashboardSort['field'],
    | 'shop_name'
    | 'turnover_cents'
    | 'order_count'
    | 'refund_order_count'
    | 'collected_at'
  > = {
    shopName: 'shop_name',
    turnoverCents: 'turnover_cents',
    orderCount: 'order_count',
    refundOrderCount: 'refund_order_count',
    collectedAt: 'collected_at',
  }
  return fields[field]
}

export const operatingDashboardApi = {
  async read(
    params: OperatingDashboardReadParams,
  ): Promise<OperatingDashboardRead> {
    const response = await httpClient.get<DashboardReadDto>(basePath, {
      params: {
        start_date: params.range.startDate,
        end_date: params.range.endDate,
        ...(params.filters.platform
          ? { platform: params.filters.platform }
          : {}),
        ...(params.filters.shopId ? { shop_id: params.filters.shopId } : {}),
        ...(params.sort
          ? {
              sort_field: toApiSortField(params.sort.field),
              sort_direction: params.sort.direction,
            }
          : {}),
        page: params.page,
        page_size: params.pageSize,
      },
    })
    return mapOperatingDashboardRead(response.data)
  },

  async requestCollectionUpdate(params: {
    range: OperatingDashboardDateRange
    filters: OperatingDashboardFilters
    forceRecollect?: boolean
  }): Promise<OperatingDashboardCollectionSubmission> {
    const response =
      await httpClient.post<OperatingDashboardCollectionSubmissionDto>(
        `${basePath}/collections${params.forceRecollect ? '/recollect' : ''}`,
        {
          start_date: params.range.startDate,
          end_date: params.range.endDate,
          ...(params.filters.platform
            ? { platform: params.filters.platform }
            : {}),
          ...(params.filters.shopId ? { shop_id: params.filters.shopId } : {}),
        },
      )
    return mapCollectionSubmission(response.data)
  },

  async getCollection(
    collectionJobId: string,
  ): Promise<OperatingDashboardCollectionJobDto> {
    const response = await httpClient.get<OperatingDashboardCollectionJobDto>(
      `${basePath}/collections/${encodeURIComponent(collectionJobId)}`,
    )
    return response.data
  },

  async recoverCollectionItem(params: {
    collectionJobId: string
    collectionItemId: string
    sessionVersion: number
    requiresValidation?: boolean
  }): Promise<OperatingDashboardCollectionJobDto> {
    const response = await httpClient.post<OperatingDashboardCollectionJobDto>(
      `${basePath}/collections/${encodeURIComponent(params.collectionJobId)}/retry`,
      {
        item_ids: [params.collectionItemId],
        session_recovery_version: params.sessionVersion,
        ...(params.requiresValidation
          ? { revalidate_current_session: true }
          : {}),
      },
    )
    return response.data
  },
}
