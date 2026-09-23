import type { ShopPlatform } from '@/entities/shop'

/**
 * Dashboard view state.  Mock records use this shape directly; real API DTOs
 * are mapped into it at the feature boundary rather than leaked into page UI.
 */
export type OperatingDashboardDatePreset =
  'yesterday' | 'last3Days' | 'last7Days' | 'last30Days' | 'custom'

export interface OperatingDashboardFilters {
  datePreset: OperatingDashboardDatePreset
  /** Naive UI epoch values; interpreted as Asia/Shanghai calendar dates. */
  customDateRange: [number, number] | null
  platform: ShopPlatform | null
  shopId: string | null
}

export interface OperatingDashboardDateRange {
  startDate: string
  endDate: string
}

export interface MerchantExperienceScore {
  totalScore: number
  productScore: number | null
  logisticsScore: number | null
  serviceScore: number | null
  collectedAt: string
}

/** One platform-read observation for a shop and one Shanghai business date. */
export interface OperatingDashboardRecord {
  shopId: string
  shopName: string
  platform: ShopPlatform
  businessDate: string
  turnoverCents: number | null
  orderCount: number | null
  /** UI-only mock field. It is not mapped from any current platform response. */
  returnQuantity: number | null
  experience: MerchantExperienceScore | null
  collectedAt: string | null
}

export interface OperatingDashboardShopOption {
  shopId: string
  shopName: string
  platform: ShopPlatform
}

export interface OperatingDashboardTrendPoint {
  businessDate: string
  turnoverCents: number | null
  orderCount: number | null
}

export interface OperatingDashboardTableRow {
  shopId: string
  shopName: string
  platform: ShopPlatform
  turnoverCents: number | null
  orderCount: number | null
  returnQuantity: number | null
  experience: MerchantExperienceScore | null
  collectedAt: string | null
}

/** Pagination is supplied by the real API; Mock mode derives it after sort. */
export interface OperatingDashboardTablePage {
  total: number
  page: number
  pageSize: number
}

export type OperatingDashboardCoverageState =
  | 'missing'
  | 'collecting'
  | 'waiting_reauthorization'
  | 'failed'

export interface OperatingDashboardCoverageMissing {
  shopId: string
  shopName: string
  businessDate: string
  state: OperatingDashboardCoverageState
}

/**
 * Database-read collection coverage for the current authorized filter scope.
 * It never means that this page has started a platform request.
 */
export interface OperatingDashboardCoverage {
  state: 'available' | 'unsupported'
  supportedShopCount: number
  collectedShopDays: number
  totalShopDays: number
  missingShopDays: number
  missingSamples: OperatingDashboardCoverageMissing[]
  missingSamplesTruncated: boolean
  manualBackfillRequired: boolean
}

/**
 * UI-only table ordering. A future Real operating-data Page must apply the
 * same field and direction within the authorized scope before pagination.
 */
export type OperatingDashboardSortField =
  'shopName' | 'turnoverCents' | 'orderCount' | 'returnQuantity' | 'collectedAt'

export type OperatingDashboardSortDirection = 'asc' | 'desc'

export interface OperatingDashboardSort {
  field: OperatingDashboardSortField
  direction: OperatingDashboardSortDirection
}

export type DashboardComparison =
  | { state: 'unavailable' }
  | { state: 'equal' }
  | {
      state: 'increase' | 'decrease'
      percentage: number
      favorable: boolean
    }

export interface OperatingDashboardSummary {
  turnoverCents: number | null
  orderCount: number | null
  returnQuantity: number | null
  /** Null means the authorized shop scope could not be read. */
  shopCount: number | null
  turnoverComparison: DashboardComparison
  orderComparison: DashboardComparison
  returnComparison: DashboardComparison
  /** Shop count has no confirmed historical baseline in V1. */
  shopCountComparison: DashboardComparison
}

export interface OperatingDashboardRead {
  dateRange: OperatingDashboardDateRange
  comparisonDateRange: OperatingDashboardDateRange
  trendDateRange: OperatingDashboardDateRange
  /** All shops present in this UI-only data source before platform selection. */
  allAvailableShops: OperatingDashboardShopOption[]
  /** Shop candidates compatible with the current platform selection. */
  availableShops: OperatingDashboardShopOption[]
  summary: OperatingDashboardSummary
  trend: OperatingDashboardTrendPoint[]
  tableRows: OperatingDashboardTableRow[]
  tablePage: OperatingDashboardTablePage
  coverage: OperatingDashboardCoverage
  /** True only when this Backend is allowed to execute platform collection. */
  collectionAvailable: boolean
}

export interface OperatingDashboardRefreshResult {
  status: 'completed' | 'partial_failure' | 'failed'
  attemptedShopCount: number
  refreshedShopCount: number
  failedShopNames: string[]
}

export interface OperatingDashboardMockSource {
  read(filters: OperatingDashboardFilters): Promise<OperatingDashboardRead>
  refresh(
    filters: OperatingDashboardFilters,
  ): Promise<OperatingDashboardRefreshResult>
}
