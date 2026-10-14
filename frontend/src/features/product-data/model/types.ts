import type { ApiMode, PageResult } from '@/shared/api'

export const PRODUCT_METRICS = [
  { id: 'product_show_ucnt', label: '曝光人数', format: 'count', width: 130 },
  {
    id: 'product_click_pay_ucnt_ratio',
    label: '点击-成交转化率（人数）',
    format: 'ratio',
    width: 210,
  },
  { id: 'pay_cnt', label: '成交订单数', format: 'count', width: 130 },
  { id: 'receive_amt', label: '成交金额', format: 'amount', width: 150 },
  { id: 'product_click_ucnt', label: '点击人数', format: 'count', width: 130 },
  { id: 'pay_amt', label: '用户支付金额', format: 'amount', width: 150 },
  { id: 'pay_ucnt', label: '成交人数', format: 'count', width: 130 },
  {
    id: 'product_click_show_ucnt_ratio',
    label: '曝光-点击率（人数）',
    format: 'ratio',
    width: 190,
  },
  { id: 'refund_amt', label: '退款金额', format: 'amount', width: 150 },
  { id: 'refund_cnt', label: '退款订单数', format: 'count', width: 130 },
  { id: 'stock_cnt', label: '实时可售库存', format: 'count', width: 150 },
] as const

export type ProductMetricId = (typeof PRODUCT_METRICS)[number]['id']
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
  { id: 'selling', label: '售卖状态', width: 120 },
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
  selling: 'on-sale' | 'off-sale'
  carrier: 'card' | 'video' | 'live'
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
  minExposure: number | null
  minOrders: number | null
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
