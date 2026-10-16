// Frontend semantic registry only. IDs (including historical code-shaped IDs)
// are NOT wire fields. platformCode/rawUnitCode record a verified single-page
// observation, not a unit converter or Real API mapper. Real remains unavailable.
interface MetricDefinition {
  id: string
  label: string
  officialLabel: string
  aliases: readonly string[]
  format: 'count' | 'ratio' | 'amount'
  width: number
  note?: string
  platformCode?: string
  rawUnitCode?: 3 | 4 | 5
}
interface VerifiedPrimaryMetricDefinition extends MetricDefinition {
  platformCode: string
  rawUnitCode: 3 | 4 | 5
}

export const PRIMARY_PRODUCT_METRICS = [
  {
    id: 'exposureCount',
    label: '曝光',
    officialLabel: '商品曝光次数',
    platformCode: 'product_show_cnt',
    rawUnitCode: 5,
    aliases: [],
    format: 'count',
    width: 130,
  },
  {
    id: 'clickCount',
    label: '点击量',
    officialLabel: '商品点击次数',
    platformCode: 'product_click_cnt',
    rawUnitCode: 5,
    aliases: [],
    format: 'count',
    width: 130,
  },
  {
    id: 'exposureClickRate',
    label: '点击率',
    officialLabel: '曝光点击率（人数）',
    platformCode: 'product_show_click_converse_uv_rate',
    rawUnitCode: 4,
    aliases: ['曝光点击率'],
    format: 'ratio',
    width: 130,
  },
  {
    id: 'cartUsers',
    label: '加购量',
    officialLabel: '加购人数',
    platformCode: 'click_add_to_cart_uv',
    rawUnitCode: 5,
    aliases: [],
    format: 'count',
    width: 130,
    note: '人数，不是加购次数。',
  },
  {
    id: 'visitCartRate',
    label: '加购率',
    officialLabel: '访问加购转化率',
    platformCode: 'product_add_show_converse_uv_ratio',
    rawUnitCode: 4,
    aliases: [],
    format: 'ratio',
    width: 130,
  },
  {
    id: 'netOrders',
    label: '真实订单',
    officialLabel: '净成交订单数',
    platformCode: 'net_pay_cnt',
    rawUnitCode: 5,
    aliases: [],
    format: 'count',
    width: 130,
    note: '具体退款处理口径待核验；不由其他订单数相减推算。',
  },
  {
    id: 'refundRelatedOrders',
    label: '异常订单',
    officialLabel: '退款后成交订单数（支付时间）',
    platformCode: 'pay_cnt_exclude_refund',
    rawUnitCode: 5,
    aliases: [],
    format: 'count',
    width: 130,
    note: '保留用户选定别名；不等同发生退款订单数，不代表违规或风控异常；不由成交、净成交或退款订单数相减推算，具体业务定义待确认。',
  },
  {
    id: 'clickPayRate',
    label: '转化率',
    officialLabel: '点击支付率（人数）',
    platformCode: 'product_click_pay_converse_uv_rate',
    rawUnitCode: 4,
    aliases: ['点击成交率'],
    format: 'ratio',
    width: 130,
  },
  {
    id: 'payTimeRefundRate',
    label: '退款率',
    officialLabel: '退款率（支付时间）',
    platformCode: 'pay_refund_ratio',
    rawUnitCode: 4,
    aliases: [],
    format: 'ratio',
    width: 130,
    note: '支付时间口径的总体退款率，包含发货前与发货后；直接使用平台总体比率，不自行相加两阶段百分比，不以仅发货后或退款时间口径替代。',
  },
  {
    id: 'pay_amt',
    label: '支付金额',
    officialLabel: '用户支付金额',
    platformCode: 'pay_amt',
    rawUnitCode: 3,
    aliases: [],
    format: 'amount',
    width: 150,
  },
  {
    id: 'pay_cnt',
    label: '订单数',
    officialLabel: '成交订单数',
    platformCode: 'pay_cnt',
    rawUnitCode: 5,
    aliases: [],
    format: 'count',
    width: 130,
  },
  {
    id: 'pay_ucnt',
    label: '成交人数',
    officialLabel: '成交人数',
    platformCode: 'pay_ucnt',
    rawUnitCode: 5,
    aliases: [],
    format: 'count',
    width: 130,
  },
  {
    id: 'payPerOrder',
    label: '客单价',
    officialLabel: '成交客单价',
    platformCode: 'per_user_price',
    rawUnitCode: 3,
    aliases: [],
    format: 'amount',
    width: 150,
    note: '保留独立指标，不在页面自行计算。',
  },
  {
    id: 'payTimeRefundAmount',
    label: '退款金额',
    officialLabel: '退款金额（支付时间）',
    platformCode: 'pay_refund_success_amt',
    rawUnitCode: 3,
    aliases: [],
    format: 'amount',
    width: 150,
  },
  {
    id: 'payTimeRefundOrders',
    label: '退款单数',
    officialLabel: '退款订单数（支付时间）',
    platformCode: 'pay_refund_success_order_cnt',
    rawUnitCode: 5,
    aliases: [],
    format: 'count',
    width: 130,
  },
  {
    id: 'product_show_ucnt',
    label: '曝光人数',
    officialLabel: '商品曝光人数',
    platformCode: 'product_show_ucnt',
    rawUnitCode: 5,
    aliases: [],
    format: 'count',
    width: 130,
  },
  {
    id: 'product_click_ucnt',
    label: '点击人数',
    officialLabel: '商品点击人数',
    platformCode: 'product_click_ucnt',
    rawUnitCode: 5,
    aliases: [],
    format: 'count',
    width: 130,
  },
] as const satisfies readonly VerifiedPrimaryMetricDefinition[]

// Verified source-code union only, not a wire DTO, unit converter or Real mapper.
export type ProductPlatformMetricCode =
  (typeof PRIMARY_PRODUCT_METRICS)[number]['platformCode']

// Preserve saved v1 column IDs and their independent meanings. In particular,
// refund_amt/refund_cnt must never become aliases of payment-time refunds.
export const LEGACY_PRODUCT_METRICS = [
  {
    id: 'receive_amt',
    label: '结算金额',
    officialLabel: '结算金额',
    aliases: [],
    format: 'amount',
    width: 150,
    note: '兼容旧列；已纠正旧版“成交金额”误标，不等同用户支付金额。',
  },
  {
    id: 'refund_amt',
    label: '退款金额（退款时间）',
    officialLabel: '退款金额（退款时间）',
    aliases: [],
    format: 'amount',
    width: 190,
    note: '兼容旧列，与支付时间退款分别保存。',
  },
  {
    id: 'refund_cnt',
    label: '退款订单数（旧版未核实）',
    officialLabel: '旧版退款订单数（口径未核实）',
    aliases: [],
    format: 'count',
    width: 210,
    note: '旧ID保留；数据保持未知，不替代退款时间或支付时间订单数。',
  },
  {
    id: 'stock_cnt',
    label: '实时可售库存（未核实）',
    officialLabel: '实时可售库存（未核实）',
    aliases: [],
    format: 'count',
    width: 190,
    note: '旧ID保留；数据保持未知，不从其他指标推断。',
  },
] as const satisfies readonly MetricDefinition[]

export const PRODUCT_METRICS = [
  ...PRIMARY_PRODUCT_METRICS,
  ...LEGACY_PRODUCT_METRICS,
]
export type ProductMetricId = (typeof PRODUCT_METRICS)[number]['id']

export function productMetricDefinition(id: string) {
  return PRODUCT_METRICS.find((metric) => metric.id === id)
}

export function resolveProductMetricId(value: string): ProductMetricId | null {
  return (
    PRODUCT_METRICS.find(
      (metric) =>
        metric.id === value ||
        metric.label === value ||
        (metric.aliases as readonly string[]).includes(value),
    )?.id ?? null
  )
}

export function productMetricTooltip(id: string): string {
  const metric: MetricDefinition | undefined = productMetricDefinition(id)
  if (!metric) return ''
  const evidence = metric.platformCode
    ? '字段代码已完成单页核验。' +
      (metric.rawUnitCode === 3
        ? '金额分/元显示换算待确认。'
        : metric.rawUnitCode === 4
          ? '官方页面百分比显示换算待确认。'
          : '')
    : '兼容旧列的真实字段契约待确认。'
  const aliases = metric.aliases.filter((alias) =>
    /[\u4e00-\u9fff]/.test(alias),
  )
  return (
    '官方口径：' +
    metric.officialLabel +
    '。' +
    (aliases.length ? '别名：' + aliases.join('、') + '。' : '') +
    (metric.note ?? '') +
    evidence +
    '真实接口尚未接入；演示值不是平台数据。'
  )
}
