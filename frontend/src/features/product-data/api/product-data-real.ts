import { httpClient, type PageDto } from '@/shared/api'
import { PRIMARY_PRODUCT_METRICS, PRODUCT_METRICS } from '../model/metrics'
import { compileProductRanges } from '../model/metric-ranges'
import type {
  ProductDataPage,
  ProductDataQuery,
  ProductDataRow,
  ProductDataSource,
  ProductMetric,
  ProductDataCollection,
} from '../model/types'

export interface ProductDataScopeDto {
  shop_id: string
  period: '1d' | '7d' | '30d'
  start_date: string
  end_date: string
  timezone: 'Asia/Shanghai'
  platform: 'douyin'
  sale_type: '1'
  content_type: '1'
  request_contract: 'compass_product_list_request74_v1'
  metric_contract: 'compass_product_list_core17_v1'
}
export interface ProductDataMetricDto {
  state: 'available' | 'missing' | 'null' | 'invalid'
  raw_value: string | null
  raw_unit: number | null
  unit_verified: boolean
}
export interface ProductDataRowDto {
  shop_product_id: string
  generation_id: string
  shop_id: string
  shop_name: string
  product_id: string
  title: string | null
  image_url: string | null
  metrics: Record<string, ProductDataMetricDto>
  scope: ProductDataScopeDto
  retrieved_at: string
}
export interface ProductDataPageDto extends PageDto<ProductDataRowDto> {
  coverage: {
    supported_shop_count: number
    collected_shop_count: number
    missing_shop_ids: string[]
    collection_available: boolean
    unit_unconfirmed_codes: string[]
  }
}

export interface ProductDataCollectionDto {
  generation_id: string
  scope: ProductDataScopeDto
  status: ProductDataCollection['status']
  stage: string
  received_pages: number
  expected_total: number | null
  received_total: number | null
  pages_complete: boolean
  raw_complete_rows: number | null
  unit_complete_rows: number | null
  failure_code: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
  published_at: string | null
  lease_expired: boolean
}
function mapCollection(dto: ProductDataCollectionDto): ProductDataCollection {
  return {
    id: dto.generation_id,
    period: dto.scope.period,
    startDate: dto.scope.start_date,
    endDate: dto.scope.end_date,
    status: dto.status,
    stage: dto.stage,
    receivedPages: dto.received_pages,
    expectedTotal: dto.expected_total,
    receivedTotal: dto.received_total,
    pagesComplete: dto.pages_complete,
    rawCompleteRows: dto.raw_complete_rows,
    unitCompleteRows: dto.unit_complete_rows,
    failureCode: dto.failure_code,
    createdAt: dto.created_at,
    startedAt: dto.started_at,
    finishedAt: dto.finished_at,
    publishedAt: dto.published_at,
    leaseExpired: dto.lease_expired,
  }
}

export const PRODUCT_DATA_GROUPS_UNAVAILABLE = '商品分组尚未接入'
export const PRODUCT_DATA_SCOPE_UNAVAILABLE =
  '当前仅支持基准切片及近1/7/30天，其他维度尚未接入'
export const PRODUCT_DATA_UNIT_UNCONFIRMED =
  '金额和比例显示单位待核定，暂不支持相关筛选排序'

export function productDataParams(query: ProductDataQuery) {
  const { filters, sort } = query
  if (
    filters.datePreset === 'custom' ||
    filters.groupId ||
    filters.selling ||
    filters.carrier
  )
    throw new Error(PRODUCT_DATA_SCOPE_UNAVAILABLE)
  const compiled = compileProductRanges(filters.metricRanges)
  if (Object.keys(compiled.errors).length)
    throw new Error(Object.values(compiled.errors)[0])
  const ranges = compiled.intervals.map((interval) => {
    const metric = PRIMARY_PRODUCT_METRICS.find(
      (definition) => definition.id === interval.metricId,
    )!
    if (interval.unit !== 'count')
      throw new Error(PRODUCT_DATA_UNIT_UNCONFIRMED)
    if (
      [interval.min, interval.max].some(
        (value) => value !== null && !Number.isSafeInteger(value),
      )
    )
      throw new Error('数量边界超出精确整数范围')
    return {
      metric: metric.platformCode,
      min_value: interval.min?.toString() ?? null,
      max_value: interval.max?.toString() ?? null,
    }
  })
  const sorts: Record<string, string> = {
    shop: 'shop_name',
    updatedAt: 'retrieved_at',
  }
  if (sort) {
    const metric = PRIMARY_PRODUCT_METRICS.find(
      (definition) => definition.id === sort.field,
    )
    if (metric?.format !== 'count' && metric?.platformCode)
      throw new Error(PRODUCT_DATA_UNIT_UNCONFIRMED)
    if (!sorts[sort.field] && !metric?.platformCode)
      throw new Error(PRODUCT_DATA_SCOPE_UNAVAILABLE)
    if (metric?.platformCode) sorts[sort.field] = metric.platformCode
  }
  return {
    period:
      filters.datePreset === 'last7Days'
        ? '7d'
        : filters.datePreset === 'last30Days'
          ? '30d'
          : '1d',
    start_date: query.period.startDate,
    end_date: query.period.endDate,
    shop_id: filters.shopId ?? undefined,
    product_id: filters.productId,
    product_name: filters.productName,
    sale_type: '1',
    content_type: '1',
    ranges: JSON.stringify(ranges),
    page: query.page,
    page_size: query.pageSize,
    sort_field: sort ? sorts[sort.field] : undefined,
    sort_direction: sort?.direction,
  }
}

export function mapProductDataRow(dto: ProductDataRowDto): ProductDataRow {
  if (
    dto.scope.request_contract !== 'compass_product_list_request74_v1' ||
    dto.scope.metric_contract !== 'compass_product_list_core17_v1'
  )
    throw new Error('商品数据来源版本不匹配')
  const metrics = Object.fromEntries(
    PRODUCT_METRICS.map(({ id }) => [
      id,
      { state: 'missing', value: null, unit: null } satisfies ProductMetric,
    ]),
  ) as ProductDataRow['metrics']
  for (const definition of PRIMARY_PRODUCT_METRICS) {
    const raw = dto.metrics[definition.platformCode]
    if (!raw) throw new Error('商品指标契约不完整')
    const count =
      definition.format === 'count' && raw.unit_verified && raw.raw_unit === 5
    metrics[definition.id] = {
      state:
        raw.state === 'available' && !count ? 'unit_unverified' : raw.state,
      value: count ? raw.raw_value : null,
      unit: count ? 'count' : null,
      rawValue: raw.raw_value,
      rawUnit: raw.raw_unit,
    }
  }
  return {
    id: dto.shop_product_id,
    shopId: dto.shop_id,
    shopName: dto.shop_name,
    productId: dto.product_id,
    title: dto.title ?? '—',
    imageUrl: dto.image_url,
    groupId: null,
    groupName: null,
    groupingAvailable: false,
    selling: null,
    carrier: null,
    metrics,
    period: { startDate: dto.scope.start_date, endDate: dto.scope.end_date },
    retrievedAt: dto.retrieved_at,
  }
}

export function createRealProductDataSource(): ProductDataSource {
  const groupsUnavailable = async (): Promise<never> => {
    throw new Error(PRODUCT_DATA_GROUPS_UNAVAILABLE)
  }
  return {
    mode: 'real',
    available: true,
    groupsAvailable: false,
    async collect(command) {
      const { data } = await httpClient.post<ProductDataCollectionDto>(
        '/api/v1/product-data/collections',
        {
          shop_id: command.shopId,
          period: command.period,
          submission_key: command.submissionKey,
          sale_type: '1',
          content_type: '1',
        },
      )
      return mapCollection(data)
    },
    async collection(id) {
      const { data } = await httpClient.get<ProductDataCollectionDto>(
        `/api/v1/product-data/collections/${encodeURIComponent(id)}`,
      )
      return mapCollection(data)
    },
    async list(query): Promise<ProductDataPage> {
      const { data } = await httpClient.get<ProductDataPageDto>(
        '/api/v1/product-data',
        { params: productDataParams(query) },
      )
      return {
        items: data.items.map(mapProductDataRow),
        total: data.total,
        page: data.page,
        pageSize: data.page_size,
        coverage: {
          supportedShopCount: data.coverage.supported_shop_count,
          collectedShopCount: data.coverage.collected_shop_count,
          missingShopIds: data.coverage.missing_shop_ids,
          collectionAvailable: data.coverage.collection_available,
          unitUnconfirmedCodes: data.coverage.unit_unconfirmed_codes,
        },
      }
    },
    groups: groupsUnavailable,
    saveGroup: groupsUnavailable,
    deleteGroup: groupsUnavailable,
    assignGroup: groupsUnavailable,
  }
}
