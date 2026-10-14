import { httpClient, type PageDto } from '@/shared/api'
import type {
  SelectionExecutionSummary,
  SelectionFallbackReason,
  SelectionPrimaryBusinessError,
} from '../model/contracts'
import type { SelectionRelativeDto } from './selection-strategy-api'

// Mirrors the registered SelectionObservationRead schema, not the Mock draft.
// Decimal values stay strings. Units, channel and relative-period mappings are
// deliberately not inferred here.
export interface SelectionSourceDto {
  version: 1 | 2
  platform: 'douyin'
  endpoint: 'product_rank/video_bring_good'
  business: {
    industry_id: string
    category_id: string
    brand_type: string
    price_bin: string
    search_info: string
    rank_data_type: string
    begin_date: string
    end_date: string
    date_type: string
    activity_id: string
  }
  date_selection?: {
    policy:
      | 'shanghai_7d_once'
      | 'shanghai_realtime_today'
      | 'shanghai_1d_yesterday'
      | 'shanghai_30d_complete_days'
    accepted_local_date: string
    primary_begin: string
    primary_end: string
    backup_begin: string | null
    backup_end: string | null
    actual_window: 'primary' | 'backup'
    fallback_reason: SelectionFallbackReason | null
    primary_error?: SelectionPrimaryBusinessError | null
    rank_from: number
    rank_to: number
  } | null
  first_listed_only?: true | null
}

export interface SelectionMetricDto {
  state: 'available' | 'missing' | 'null' | 'invalid'
  retrieved_at: string
  value_range:
    | [
        {
          value: string
          value_type: 'int' | 'float'
          unit: string | number | null
        },
        {
          value: string
          value_type: 'int' | 'float'
          unit: string | number | null
        },
      ]
    | null
}

export interface SelectionObservationDto {
  observation_id: string
  last_run_id: string | null
  candidate_id: string
  blocked?: boolean
  blocked_changed_at?: string | null
  discovery_state?: 'new' | 'known' | 'unknown'
  hit_at?: string | null
  result_run_id?: string | null
  basic_info_status?: SelectionBasicStatusDto | null
  product_id: string
  platform: 'douyin'
  request_shop_id: string
  request_shop_name: string
  source_scope_hash: string
  source_context: SelectionSourceDto
  period_begin: string
  period_end: string
  title: string | null
  image_url: string | null
  source_url: string | null
  merchants: { platform_shop_id: string; name: string | null }[]
  category_path: string[] | null
  price_band: string | null
  rank: number | null
  previous_rank: number | null
  previous_checked_at: string | null
  newly_on_ranking: boolean | null
  first_seen_at: string
  checked_at: string
  metrics_retrieved_at: string
  video_metric_ranges: Record<
    'pay_amt' | 'pay_combo_cnt' | 'product_click_cnt' | 'video_cnt',
    SelectionMetricDto
  >
  first_on_shelf_date: string | null
  bad_comment_rate_raw: string | null
  bad_comment_rate_unit: string | number | null
  basic_info_retrieved_at: string | null
  last_attempt_at: string
  last_error_code: string | null
  last_error_stage: string | null
}

export interface SelectionReadParams {
  page: number
  pageSize: number
  shopId?: string | null
  sourceScopeHash?: string | null
  search?: string
  sortField?: 'checked_at' | 'first_on_shelf_date' | 'rank'
  sortDirection?: 'asc' | 'desc'
  blocked?: boolean
  resultScope?: SelectionResultScope
  strategyId?: string | null
  receiptId?: string | null
}

export type SelectionResultScope = 'all' | 'today' | 'today_new' | 'today_known'
export interface SelectionBasicStatusDto {
  version: 1
  attempted_at: string
  request_started_at: string
  state: 'succeeded' | 'partial' | 'failed'
  category_path: SelectionBasicFieldDto
  first_on_shelf_date: SelectionBasicFieldDto
  bad_comment_rate: SelectionBasicFieldDto
  error_code: string | null
  error_stage: string | null
  platform_business_code: string | number | null
}
export interface SelectionBasicFieldDto {
  last_attempt_state: 'available' | 'missing' | 'null' | 'invalid' | 'unknown'
  last_success_at: string | null
}
export interface SelectionResultContextDto {
  receipt_id: string | null
  execution_run_id: string | null
  detail_state: 'recorded' | 'not_recorded' | null
  execution: SelectionExecutionSummary | null
  unknown_discovery_count: number
}
export interface SelectionBatchDto {
  receipt_id: string
  execution_run_id: string
  submitted_at: string
  detail_state: 'recorded' | 'not_recorded'
  execution: SelectionExecutionSummary
  visible_item_count?: number | null
}
export interface SelectionBasicRunDto {
  run_id: string
  operation_kind: 'basic_info'
  target_observation_id: string
  status: SelectionExecutionSummary['status']
  saved_count: 0
  supplemented_count: number
  supplement_failed_count: number
  error_code: string | null
  error_stage: string | null
  platform_business_code: string | number | null
  created_at: string
  finished_at: string | null
}
export interface SelectionBasicReceiptDto {
  receipt_id: string
  submission_key: string
  execution_run_id: string
  reused: boolean
  execution: SelectionBasicRunDto
}
export async function blockSelectionCandidate(
  id: string,
  blocked: boolean,
): Promise<SelectionObservationDto> {
  return (
    await httpClient.patch<SelectionObservationDto>(
      `${basePath}/observations/${encodeURIComponent(id)}/blocked`,
      { blocked },
    )
  ).data
}
export async function submitSelectionBasic(
  id: string,
  submissionKey: string,
): Promise<SelectionBasicReceiptDto> {
  return (
    await httpClient.post<SelectionBasicReceiptDto>(
      `${basePath}/basic-info-runs`,
      { observation_id: id, submission_key: submissionKey },
    )
  ).data
}
export async function readSelectionBasic(
  id: string,
): Promise<SelectionBasicRunDto | null> {
  return (
    await httpClient.get<SelectionBasicRunDto | null>(
      `${basePath}/observations/${encodeURIComponent(id)}/basic-info-run`,
    )
  ).data
}
export async function readSelectionBatches(
  strategyId: string,
  shopId: string | null,
): Promise<PageDto<SelectionBatchDto>> {
  return (
    await httpClient.get<PageDto<SelectionBatchDto>>(
      `${basePath}/strategies/${encodeURIComponent(strategyId)}/batches`,
      { params: { shop_id: shopId ?? undefined, page: 1, page_size: 100 } },
    )
  ).data
}

const basePath = '/api/v1/product-selection'

export interface SelectionCapabilitiesDto {
  execution_enabled: boolean
  manual_execution_available: boolean
  unavailable_reason: 'EXECUTION_DISABLED' | null
  strategy_save_available?: boolean
  schedule_available?: boolean
  schedule_execution_enabled?: boolean
  supported_periods?: ('realtime' | '1d' | '7d' | '30d')[]
  supported_brands?: ('all' | 'known' | 'unknown')[]
  custom_price_available?: boolean
  first_listed_filter_available?: boolean
  max_rank?: number
  candidate_block_available?: boolean
  basic_info_available?: boolean
}
export interface SelectionRunCreateDto extends SelectionRelativeDto {
  submission_key: string
  strategy_id?: string
  strategy_version?: number
  shop_id: string
}
export interface SelectionRunReceiptDto {
  receipt_id: string
  submission_key: string
  execution_run_id: string
  reused: boolean
  strategy?: { strategy_id: string; version: number } | null
  execution: SelectionExecutionSummary
}
export async function readSelectionCapabilities(): Promise<SelectionCapabilitiesDto> {
  return (
    await httpClient.get<SelectionCapabilitiesDto>(`${basePath}/capabilities`)
  ).data
}
export async function submitSelectionRun(
  command: SelectionRunCreateDto,
): Promise<SelectionRunReceiptDto> {
  return (
    await httpClient.post<SelectionRunReceiptDto>(`${basePath}/runs`, command)
  ).data
}

export interface SelectionCategoryDto {
  category_id: string
  name: string
  children: SelectionCategoryDto[]
}

export interface SelectionCategoriesDto {
  shop_id: string
  nodes: SelectionCategoryDto[]
  industry_id: string | null
  industry_name: string | null
  selected_category_id: string | null
}

export async function readSelectionCategories(
  shopId: string,
  options?: { refresh?: boolean },
): Promise<SelectionCategoriesDto> {
  const response = await httpClient.get<SelectionCategoriesDto>(
    `${basePath}/categories`,
    {
      params: {
        shop_id: shopId,
        ...(options?.refresh ? { refresh: true } : {}),
      },
    },
  )
  return response.data
}

export async function readLatestSelectionRun(
  shopId: string | null,
): Promise<SelectionExecutionSummary | null> {
  const response = await httpClient.get<PageDto<SelectionExecutionSummary>>(
    `${basePath}/runs`,
    {
      params: { shop_id: shopId ?? undefined, page: 1, page_size: 1 },
    },
  )
  return response.data.items[0] ?? null
}

export async function readSelectionRun(
  runId: string,
): Promise<SelectionExecutionSummary> {
  const response = await httpClient.get<SelectionExecutionSummary>(
    `${basePath}/runs/${encodeURIComponent(runId)}`,
  )
  return response.data
}

export async function readSelectionCandidates(
  params: SelectionReadParams,
): Promise<
  PageDto<SelectionObservationDto> & { context?: SelectionResultContextDto }
> {
  const response = await httpClient.get<
    PageDto<SelectionObservationDto> & { context?: SelectionResultContextDto }
  >(`${basePath}/candidates`, {
    params: {
      page: params.page,
      page_size: params.pageSize,
      shop_id: params.shopId ?? undefined,
      source_scope_hash: params.sourceScopeHash ?? undefined,
      search: params.search || undefined,
      sort_field: params.sortField ?? 'checked_at',
      sort_direction: params.sortDirection ?? 'desc',
      blocked: params.blocked ?? false,
      result_scope: params.resultScope ?? 'all',
      strategy_id: params.strategyId ?? undefined,
      receipt_id: params.receiptId ?? undefined,
    },
  })
  return response.data
}

export async function readSelectionObservation(
  observationId: string,
  receiptId?: string | null,
): Promise<SelectionObservationDto> {
  const response = await httpClient.get<SelectionObservationDto>(
    `${basePath}/observations/${encodeURIComponent(observationId)}`,
    { params: { receipt_id: receiptId ?? undefined } },
  )
  return response.data
}
