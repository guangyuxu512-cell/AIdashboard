import type { ApiMode, PageResult } from '@/shared/api'
import { PRODUCT_METRICS, type ProductMetricId } from './metrics'
import type { ProductRangeDrafts } from './metric-ranges'
export { PRODUCT_METRICS, type ProductMetricId } from './metrics'
export type ProductMetricState = 'available' | 'missing' | 'null' | 'invalid'
export interface ProductMetric {
  state: ProductMetricState
  value: string | null
  unit: 'count' | 'ratio' | 'yuan' | null
}
export const PRODUCT_COLUMNS = [
  { id: 'shop', label: '店铺', width: 140 },
  { id: 'group', label: '商品分组', width: 120 },
  ...PRODUCT_METRICS,
  { id: 'selling', label: '售卖类型', width: 120 },
  { id: 'carrier', label: '商品载体', width: 120 },
  { id: 'updatedAt', label: '数据时间', width: 170 },
] as const
export type ProductColumnId = (typeof PRODUCT_COLUMNS)[number]['id']
export const DEFAULT_PRODUCT_COLUMNS: ProductColumnId[] = [
  'shop',
  'group',
  'product_show_ucnt',
  'product_click_pay_ucnt_ratio',
  'pay_cnt',
  'receive_amt',
]
export interface ProductDataRow {
  id: string
  shopId: string
  shopName: string
  productId: string
  title: string
  imageUrl: string | null
  groupId: string | null
  groupName: string | null
  selling: 'self' | 'cooperation'
  carrier: 'card' | 'video' | 'live' | 'image-text'
  metrics: Record<ProductMetricId, ProductMetric>
  period: { startDate: string; endDate: string }
  retrievedAt: string
}
export interface ProductGroup {
  id: string
  shopId: string
  name: string
  productCount: number
}
export interface ProductDataFilters {
  shopId: string | null
  productId: string
  productName: string
  groupId: string | null
  selling: ProductDataRow['selling'] | null
  carrier: ProductDataRow['carrier'] | null
  datePreset: 'yesterday' | 'last7Days' | 'last30Days' | 'custom'
  customDateRange: [number, number] | null
  metricRanges: ProductRangeDrafts
}
export interface ProductDataQuery {
  filters: ProductDataFilters
  period: ProductDataRow['period']
  page: number
  pageSize: number
  sort: { field: ProductColumnId; direction: 'asc' | 'desc' } | null
}
export interface ProductDataSource {
  readonly mode: ApiMode
  readonly available: boolean
  list(query: ProductDataQuery): Promise<PageResult<ProductDataRow>>
  groups(shopId: string): Promise<ProductGroup[]>
  saveGroup(
    shopId: string,
    input: { id: string | null; name: string },
  ): Promise<ProductGroup>
  deleteGroup(shopId: string, groupId: string): Promise<void>
  assignGroup(
    shopId: string,
    productIds: string[],
    groupId: string | null,
  ): Promise<void>
}
