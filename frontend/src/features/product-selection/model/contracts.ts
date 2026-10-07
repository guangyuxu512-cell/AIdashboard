import type { PageResult } from '@/shared/api'

// Frontend draft only. No Backend DTO/Endpoint or platform unit is implied.
export type SelectionChannel = 'short-video' | 'baiying'
export type SelectionPeriod = 'realtime' | '1d' | '7d' | '30d'
export interface CategoryNode {
  id: string
  name: string
  children?: CategoryNode[]
}
export interface StrategyInput {
  name: string
  shopId: string | null
  creatorId: string | null
  channel: SelectionChannel
  categoryId: string | null
  period: SelectionPeriod
  brand: 'all' | 'known' | 'unknown'
  priceMode: 'all' | 'custom'
  priceAbove: number | null
  priceBelow: number | null
  firstListedOnly: boolean
  rankFrom: number | null
  rankTo: number | null
  scheduled: boolean
  scheduleKind: 'hourly' | 'daily'
  dailyTime: string
  enabled: boolean
}
export interface SelectionStrategy extends StrategyInput {
  id: string
  shopName: string
  creatorName: string
  latestResult: string | null
}
export interface SelectionCandidate {
  id: string
  shopId: string
  shopName: string
  imageUrl: string | null
  title: string
  productId: string
  category: string
  priceBand: string | null
  listedAt: string | null
  negativeReviewRate: number | null
  blocked: boolean
  source: string
  statisticalPeriod: string
  rank: number | null
  firstListed: boolean | null
  userPaidAmountRange: string | null
  userPaidAmountUnit: string | null
  clicksRange: string | null
  soldUnitsRange: string | null
  videoCountRange: string | null
}
export interface CandidateQuery {
  page: number
  pageSize: number
  shopId: string | null
  keyword: string
  blocked: boolean
  sortField: 'listedAt' | 'negativeReviewRate' | null
  sortOrder: 'ascend' | 'descend' | false
}
export interface DemoReceipt {
  mode: 'mock'
  message: string
  count: number
}
export interface SelectionService {
  readonly available: boolean
  categories(shopId: string): Promise<CategoryNode[]>
  strategies(): Promise<SelectionStrategy[]>
  saveStrategy(input: StrategyInput, id?: string): Promise<SelectionStrategy>
  retrieve(input: StrategyInput, strategyId?: string): Promise<DemoReceipt>
  candidates(query: CandidateQuery): Promise<PageResult<SelectionCandidate>>
  candidate(id: string): Promise<SelectionCandidate>
  demoAction(
    id: string,
    action: 'collect' | 'block' | 'restore',
  ): Promise<DemoReceipt>
}
export const CREATOR_DEMO_OPTIONS = [
  { label: '演示达人 A', value: 'creator-demo-a' },
  { label: '演示达人 B', value: 'creator-demo-b' },
]
export const CHANNEL_OPTIONS = [
  { label: '短视频榜单', value: 'short-video' },
  { label: '巨量百应', value: 'baiying' },
]
export function emptyStrategy(): StrategyInput {
  return {
    name: '',
    shopId: null,
    creatorId: null,
    channel: 'short-video',
    categoryId: null,
    period: 'realtime',
    brand: 'all',
    priceMode: 'all',
    priceAbove: null,
    priceBelow: null,
    firstListedOnly: false,
    rankFrom: null,
    rankTo: null,
    scheduled: false,
    scheduleKind: 'hourly',
    dailyTime: '09:00',
    enabled: true,
  }
}
