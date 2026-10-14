import { httpClient, type PageDto } from '@/shared/api'
import type {
  SelectionExecutionSummary,
  SelectionPeriod,
} from '../model/contracts'

// Mirrors strategy_contract.py/OpenAPI; relative intent, not frozen run dates.
export interface SelectionRelativeDto {
  channel: 'short-video' | 'baiying'
  period: SelectionPeriod
  industry_id: string
  category_ids: string[]
  brand: 'all' | 'known' | 'unknown'
  price_mode: 'all' | 'custom'
  price_above: string | null
  price_below: string | null
  first_listed_only: boolean
  rank_from: number
  rank_to: number
}
export interface SelectionStrategyWriteDto {
  name: string
  shop_id: string
  enabled: boolean
  conditions: { version: 1; request: SelectionRelativeDto }
  schedule: {
    scheduled: boolean
    kind: 'hourly' | 'daily'
    interval_hours?: number
    daily_time: string
    timezone: 'Asia/Shanghai'
  }
}
export interface SelectionStrategyDto extends SelectionStrategyWriteDto {
  strategy_id: string
  team_id: string
  created_by_user_id: string
  shop_name: string
  version: number
  schedule_available: boolean
  schedule_execution_enabled?: boolean
  next_run_at: string | null
  latest_run: SelectionExecutionSummary | null
  latest_trigger?: SelectionStrategyTriggerDto | null
  created_at: string
  updated_at: string
}
export interface SelectionStrategyTriggerDto {
  schedule_run_id: string
  scheduled_for: string
  created_at: string
  trigger_result: 'selection_run' | 'blocked'
  receipt_id: string | null
  execution_run_id: string | null
  error_code: string | null
  error_stage: string | null
}
const path = '/api/v1/product-selection/strategies'
export async function readStrategies(params: {
  page: number
  pageSize: number
  search: string
}): Promise<PageDto<SelectionStrategyDto>> {
  return (
    await httpClient.get<PageDto<SelectionStrategyDto>>(path, {
      params: {
        page: params.page,
        page_size: params.pageSize,
        search: params.search || undefined,
      },
    })
  ).data
}
export async function writeStrategy(
  command: SelectionStrategyWriteDto,
  id?: string,
  expectedVersion?: number,
): Promise<SelectionStrategyDto> {
  if (!id)
    return (await httpClient.post<SelectionStrategyDto>(path, command)).data
  if (!expectedVersion)
    throw new Error('请刷新已保存的策略版本，当前草稿未保存')
  return (
    await httpClient.put<SelectionStrategyDto>(
      `${path}/${encodeURIComponent(id)}`,
      { ...command, expected_version: expectedVersion },
    )
  ).data
}
export async function toggleSavedStrategy(
  id: string,
  enabled: boolean,
  expectedVersion: number,
): Promise<SelectionStrategyDto> {
  return (
    await httpClient.patch<SelectionStrategyDto>(
      `${path}/${encodeURIComponent(id)}/enabled`,
      { enabled, expected_version: expectedVersion },
    )
  ).data
}
