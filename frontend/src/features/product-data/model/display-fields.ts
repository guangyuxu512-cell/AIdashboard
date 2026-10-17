import { productMetricDefinition, type PrimaryProductMetricId } from './metrics'

export const PRODUCT_DATA_FIELD_GROUPS = [
  { id: 'basic', label: '基础字段' },
  { id: 'core', label: '核心指标' },
  { id: 'transaction', label: '交易指标' },
  { id: 'traffic', label: '流量指标' },
] as const

export type ProductDataFieldGroupId =
  (typeof PRODUCT_DATA_FIELD_GROUPS)[number]['id']

function metricField<
  const Id extends string,
  const MetricId extends PrimaryProductMetricId,
  const Group extends ProductDataFieldGroupId,
>(id: Id, metricId: MetricId, group: Group, label?: string) {
  const metric = productMetricDefinition(metricId)
  if (!metric) throw new Error(`Unknown product metric: ${metricId}`)
  return {
    id,
    label: label ?? metric.label,
    width: metric.width,
    group,
    metricId,
  }
}

// Presentation-only whitelist. Metric labels, widths, values, units and API
// codes remain owned by the existing metric registry. The two traffic aliases
// deliberately point at existing metrics and never create another data field.
export const PRODUCT_DISPLAY_COLUMNS = [
  {
    id: 'shop',
    label: '店铺',
    width: 140,
    group: 'basic',
    metricId: null,
  },
  metricField('exposureCount', 'exposureCount', 'core'),
  metricField('clickCount', 'clickCount', 'core'),
  metricField('exposureClickRate', 'exposureClickRate', 'core'),
  metricField('cartUsers', 'cartUsers', 'core'),
  metricField('visitCartRate', 'visitCartRate', 'core'),
  metricField('netOrders', 'netOrders', 'core'),
  metricField('refundRelatedOrders', 'refundRelatedOrders', 'core'),
  metricField('clickPayRate', 'clickPayRate', 'core'),
  metricField('payTimeRefundRate', 'payTimeRefundRate', 'core'),
  metricField('pay_amt', 'pay_amt', 'transaction'),
  metricField('pay_cnt', 'pay_cnt', 'transaction'),
  metricField('pay_ucnt', 'pay_ucnt', 'transaction'),
  metricField('payPerOrder', 'payPerOrder', 'transaction'),
  metricField('payTimeRefundAmount', 'payTimeRefundAmount', 'transaction'),
  metricField('payTimeRefundOrders', 'payTimeRefundOrders', 'transaction'),
  metricField('product_show_ucnt', 'product_show_ucnt', 'traffic'),
  metricField('product_click_ucnt', 'product_click_ucnt', 'traffic'),
  metricField(
    'trafficExposureClickRate',
    'exposureClickRate',
    'traffic',
    '曝光点击率',
  ),
  metricField('trafficClickPayRate', 'clickPayRate', 'traffic', '点击成交率'),
] as const

export type ProductDisplayColumn = (typeof PRODUCT_DISPLAY_COLUMNS)[number]
export type ProductDisplayColumnId = ProductDisplayColumn['id']

export const DEFAULT_PRODUCT_COLUMNS: ProductDisplayColumnId[] =
  PRODUCT_DISPLAY_COLUMNS.filter(
    ({ group }) => group === 'basic' || group === 'core',
  ).map(({ id }) => id)

export function productDisplayColumn(
  id: string,
): ProductDisplayColumn | undefined {
  return PRODUCT_DISPLAY_COLUMNS.find((column) => column.id === id)
}

export function productDisplayMetricId(
  id: string,
): PrimaryProductMetricId | null {
  return productDisplayColumn(id)?.metricId ?? null
}

export function orderProductDisplayColumns(
  ids: Iterable<string>,
): ProductDisplayColumnId[] {
  const selected = new Set(ids)
  return PRODUCT_DISPLAY_COLUMNS.filter(({ id }) => selected.has(id)).map(
    ({ id }) => id,
  )
}
