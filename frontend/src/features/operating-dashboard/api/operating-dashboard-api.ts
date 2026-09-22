import type { ShopPlatform } from '@/entities/shop'
import { httpClient } from '@/shared/api'

import type {
  DashboardComparison,
  OperatingDashboardDateRange,
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
  return_quantity: number | null
  experience_score: null
  collected_at: string | null
  coverage_complete: boolean
}

interface DashboardReadDto {
  date_range: DateRangeDto
  comparison_date_range: DateRangeDto
  trend_date_range: DateRangeDto
  all_available_shops: ShopOptionDto[]
  summary: {
    turnover_cents: number | null
    order_count: number | null
    return_quantity: number | null
    shop_count: number
    turnover_comparison: ComparisonDto
    order_comparison: ComparisonDto
    return_comparison: ComparisonDto
    shop_count_comparison: ComparisonDto
  }
  trend: Array<{
    business_date: string
    turnover_cents: number | null
    order_count: number | null
  }>
  table: {
    items: TableRowDto[]
    total: number
    page: number
    page_size: number
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
    returnQuantity: value.return_quantity,
    // Merchant experience has no verified platform contract in V1.  The
    // backend deliberately returns null rather than a guessed score object.
    experience: null,
    collectedAt: value.collected_at,
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
      returnQuantity: value.summary.return_quantity,
      shopCount: value.summary.shop_count,
      turnoverComparison: mapComparison(value.summary.turnover_comparison),
      orderComparison: mapComparison(value.summary.order_comparison),
      returnComparison: mapComparison(value.summary.return_comparison),
      shopCountComparison: mapComparison(value.summary.shop_count_comparison),
    },
    trend: value.trend.map((point) => ({
      businessDate: point.business_date,
      turnoverCents: point.turnover_cents,
      orderCount: point.order_count,
    })),
    tableRows: value.table.items.map(mapTableRow),
    tablePage: {
      total: value.table.total,
      page: value.table.page,
      pageSize: value.table.page_size,
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
  | 'return_quantity'
  | 'collected_at' {
  const fields: Record<
    OperatingDashboardSort['field'],
    | 'shop_name'
    | 'turnover_cents'
    | 'order_count'
    | 'return_quantity'
    | 'collected_at'
  > = {
    shopName: 'shop_name',
    turnoverCents: 'turnover_cents',
    orderCount: 'order_count',
    returnQuantity: 'return_quantity',
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

  async enqueueCollection(params: {
    range: OperatingDashboardDateRange
    filters: OperatingDashboardFilters
  }): Promise<OperatingDashboardCollectionJobDto> {
    const response = await httpClient.post<OperatingDashboardCollectionJobDto>(
      `${basePath}/collections`,
      {
        start_date: params.range.startDate,
        end_date: params.range.endDate,
        ...(params.filters.platform
          ? { platform: params.filters.platform }
          : {}),
        ...(params.filters.shopId ? { shop_id: params.filters.shopId } : {}),
      },
    )
    return response.data
  },

  async getCollection(
    collectionJobId: string,
  ): Promise<OperatingDashboardCollectionJobDto> {
    const response = await httpClient.get<OperatingDashboardCollectionJobDto>(
      `${basePath}/collections/${encodeURIComponent(collectionJobId)}`,
    )
    return response.data
  },
}
