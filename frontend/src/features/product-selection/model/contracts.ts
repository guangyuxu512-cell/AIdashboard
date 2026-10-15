import type { PageResult } from '@/shared/api'
import type {
  SelectionRunReceiptDto,
  SelectionCapabilitiesDto,
  SelectionBasicStatusDto,
  SelectionBasicReceiptDto,
  SelectionBasicRunDto,
  SelectionBatchDto,
  SelectionResultContextDto,
  SelectionResultScope,
} from '../api/selection-read-api'

// Frontend draft only. No Backend DTO/Endpoint or platform unit is implied.
export type SelectionChannel = 'short-video' | 'baiying'
export type SelectionPeriod = 'realtime' | '1d' | '7d' | '30d'
// Display-only Mock example, never a platform request or saved execution range.
export interface SelectionPeriodPreview {
  mode: 'mock'
  rangeLabel: string
}
export interface CategoryNode {
  id: string
  name: string
  children?: CategoryNode[]
  requestScope?: { industryId: string; categoryIds: string[] }
}
export interface ShortVideoConditions {
  categoryId: string | null
  period: SelectionPeriod
  brand: 'all' | 'known' | 'unknown'
  priceMode: 'all' | 'custom'
  priceAbove: number | null
  priceBelow: number | null
  firstListedOnly: boolean
  rankFrom: number | null
  rankTo: number | null
}
export interface StrategyInput {
  name: string
  shopId: string | null
  creatorId: string | null
  channels: {
    shortVideo: { selected: boolean; conditions: ShortVideoConditions }
    baiying: { selected: boolean; conditions: Record<string, never> }
  }
  scheduled: boolean
  scheduleKind: 'hourly' | 'daily'
  hourlyInterval: number
  dailyTime: string
  enabled: boolean
}
export interface SelectionStrategy extends StrategyInput {
  id: string
  shopName: string
  creatorName: string
  latestResult: string | null
  version?: number
  latestExecution?: SelectionExecutionSummary | null
  latestReceiptId?: string | null
  scheduleAvailable?: boolean
  scheduleExecutionEnabled?: boolean
  nextRunAt?: string | null
  latestTrigger?:
    import('../api/selection-strategy-api').SelectionStrategyTriggerDto | null
  requestScope?: { industryId: string; categoryIds: string[] }
}
export interface CandidateSourceContext {
  leaderboardId: string
  leaderboardName: string
  // Includes category, period and rank measure; only identical scopes are comparable.
  scopeKey: string
  category: string
  statisticalPeriod: string
  periodLabel: string
  rankFrom: number | null
  rankTo: number | null
  checkedAt: string | null
  dateFallback?: boolean
}
export interface CandidateMerchant {
  // Product merchant platform ID, never the requesting Shop UUID.
  shopId: string
  name: string
  competitor: boolean
}
export type CandidateDiscovery =
  'new-in-scope' | 'known' | 'outside-scope' | 'unknown'
export type MaterialCollectionStatus =
  'not-collected' | 'demo-collected' | 'failed' | 'unknown'
export interface SelectionCandidate {
  id: string
  shopId: string
  shopName: string
  merchant: CandidateMerchant | null
  imageUrl: string | null
  title: string
  productId: string
  sourceUrl: string | null
  category: string
  priceBand: string | null
  listedAt: string | null
  negativeReviewRate: number | null
  // Real ratio remains an exact decimal string until its unit is confirmed.
  negativeReviewRateRaw?: { value: string; unit: string | number | null } | null
  basicInfoError?: string | null
  basicInfoStatus?: SelectionBasicStatusDto | null
  resultRunId?: string | null
  blocked: boolean
  source: string
  sourceContext: CandidateSourceContext
  rank: number | null
  previousRank: {
    rank: number
    leaderboardId: string
    scopeKey: string
    checkedAt: string | null
  } | null
  discovery: CandidateDiscovery
  firstDiscoveredAt: string | null
  metricsRetrievedAt: string | null
  collectionStatus: MaterialCollectionStatus
  firstListed: boolean | null
  userPaidAmountRange: string | null
  userPaidAmountUnit: string | null
  clicksRange: string | null
  soldUnitsRange: string | null
  videoCountRange: string | null
}
export type CandidatePage = PageResult<SelectionCandidate> & {
  context?: SelectionResultContextDto
}
export interface CandidateQuery {
  page: number
  pageSize: number
  shopId: string | null
  keyword: string
  blocked: boolean
  sortField: 'listedAt' | 'negativeReviewRate' | null
  sortOrder: 'ascend' | 'descend' | false
  resultScope?: SelectionResultScope
  strategyId?: string | null
  receiptId?: string | null
}
export interface DemoReceipt {
  mode: 'mock'
  message: string
  count: number
  channels?: {
    channel: SelectionChannel
    state: 'demo' | 'unavailable'
    count: number | null
  }[]
}
export interface BatchCollectItemResult {
  candidateId: string
  productId: string | null
  state: 'demo' | 'failed'
  message: string
}
export interface BatchCollectReceipt {
  mode: 'mock'
  // One result per distinct product; all supplied candidate aliases are returned.
  results: (BatchCollectItemResult & { candidateIds: string[] })[]
}
export interface SelectionService {
  readonly available: boolean
  readonly strategySaveAvailable?: boolean
  readonly scheduleAvailable?: boolean
  readonly candidatesAvailable?: boolean
  readonly candidateBlockAvailable?: boolean
  batches?(
    strategyId: string,
    shopId: string | null,
  ): Promise<SelectionBatchDto[]>
  blockCandidate?(id: string, blocked: boolean): Promise<void>
  basic?: {
    submit(id: string, submissionKey: string): Promise<SelectionBasicReceiptDto>
    latest(id: string): Promise<SelectionBasicRunDto | null>
  }
  latestRun?(shopId: string | null): Promise<SelectionExecutionSummary | null>
  run?(runId: string): Promise<SelectionExecutionSummary>
  manual?: {
    capabilities(): Promise<SelectionCapabilitiesDto>
    submit(
      input: StrategyInput,
      submissionKey: string,
      categories?: CategoryNode[],
      strategy?: { id: string; version: number },
    ): Promise<SelectionRunReceiptDto>
  }
  previewPeriod(period: SelectionPeriod): Promise<SelectionPeriodPreview>
  categories(
    shopId: string,
    options?: { refresh?: boolean },
  ): Promise<CategoryNode[]>
  strategies(): Promise<SelectionStrategy[]>
  strategy?(id: string): Promise<SelectionStrategy>
  strategiesPage?(query: {
    page: number
    pageSize: number
    search: string
  }): Promise<PageResult<SelectionStrategy>>
  saveStrategy(
    input: StrategyInput,
    id?: string,
    expectedVersion?: number,
    categories?: CategoryNode[],
  ): Promise<SelectionStrategy>
  toggleStrategy?(
    row: SelectionStrategy,
    enabled: boolean,
  ): Promise<SelectionStrategy>
  retrieve(input: StrategyInput, strategyId?: string): Promise<DemoReceipt>
  candidates(query: CandidateQuery): Promise<CandidatePage>
  candidate(id: string, receiptId?: string | null): Promise<SelectionCandidate>
  demoAction(
    id: string,
    action: 'collect' | 'block' | 'restore',
  ): Promise<DemoReceipt>
  collectBatch(candidateIds: string[]): Promise<BatchCollectReceipt>
  updateCompassMetrics(id: string): Promise<DemoReceipt>
  markCompetitor(merchantShopId: string): Promise<DemoReceipt>
}
export type SelectionFallbackReason =
  'primary_success_empty' | 'primary_business_rejection_probe'
export interface SelectionPrimaryBusinessError {
  error_code: 'DOUYIN_SELECTION_BUSINESS_REJECTED'
  error_stage: 'platform_business'
  platform_business_code: 621000704 | '621000704'
}
export interface SelectionExecutionSummary {
  run_id: string
  request_shop_id: string
  status:
    'pending' | 'running' | 'succeeded' | 'partial' | 'failed' | 'interrupted'
  result_count: number | null
  saved_count: number
  supplement_failed_count: number
  error_code: string | null
  error_stage?: string | null
  platform_business_code?: string | number | null
  request_conditions?: {
    version: 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8
    scope: { begin_date: string; end_date: string }
    date_plan?: {
      backup_scope?: { begin_date: string; end_date: string }
    } | null
    date_outcome?: {
      state:
        | 'primary'
        | 'fallback_checking'
        | 'backup'
        | 'backup_empty'
        | 'both_empty'
        | 'fallback_failed'
      fallback_reason?: SelectionFallbackReason | null
      primary_error?: SelectionPrimaryBusinessError | null
    } | null
  }
}
export const CREATOR_DEMO_OPTIONS =
  import.meta.env.VITE_API_MODE === 'mock'
    ? [
        { label: '演示达人 A', value: 'creator-demo-a' },
        { label: '演示达人 B', value: 'creator-demo-b' },
      ]
    : []
export const CHANNEL_OPTIONS = [
  { label: '短视频榜单', value: 'short-video' },
  { label: '巨量百应', value: 'baiying' },
]
export function emptyStrategy(): StrategyInput {
  return {
    name: '',
    shopId: null,
    creatorId: null,
    channels: {
      shortVideo: {
        selected: true,
        conditions: {
          categoryId: null,
          period: 'realtime',
          brand: 'all',
          priceMode: 'all',
          priceAbove: null,
          priceBelow: null,
          firstListedOnly: false,
          rankFrom: null,
          rankTo: null,
        },
      },
      baiying: { selected: false, conditions: {} },
    },
    scheduled: false,
    scheduleKind: 'hourly',
    hourlyInterval: 1,
    dailyTime: '09:00',
    enabled: true,
  }
}
