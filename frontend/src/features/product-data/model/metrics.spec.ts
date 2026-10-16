import { describe, expect, it } from 'vitest'
import {
  PRIMARY_PRODUCT_METRICS,
  PRODUCT_METRICS,
  productMetricTooltip,
  resolveProductMetricId,
} from './metrics'
import { normalizeProductColumns } from './column-preferences'

describe('product metric semantic registry', () => {
  it('registers seventeen distinct primary metrics and nineteen Chinese display names without duplicate columns', () => {
    expect(PRIMARY_PRODUCT_METRICS).toHaveLength(17)
    expect(
      new Set(PRIMARY_PRODUCT_METRICS.map((metric) => metric.id)).size,
    ).toBe(17)
    expect(
      PRIMARY_PRODUCT_METRICS.flatMap((metric) => [
        metric.label,
        ...metric.aliases.filter((alias) => /[\u4e00-\u9fff]/.test(alias)),
      ]),
    ).toHaveLength(19)
    expect(
      normalizeProductColumns([
        '点击率',
        '曝光点击率',
        'exposureClickRate',
        'product_click_show_ucnt_ratio',
        '转化率',
        '点击成交率',
        'clickPayRate',
      ]),
    ).toEqual(['product_click_show_ucnt_ratio', 'product_click_pay_ucnt_ratio'])
    for (const metric of PRODUCT_METRICS)
      expect(productMetricTooltip(metric.id)).toContain(metric.officialLabel)
  })
  it('preserves old refund, settlement and unverified stock IDs rather than rebinding their meaning', () => {
    expect(
      normalizeProductColumns([
        'refund_amt',
        'refund_cnt',
        'receive_amt',
        'stock_cnt',
      ]),
    ).toEqual(['refund_amt', 'refund_cnt', 'receive_amt', 'stock_cnt'])
    expect(resolveProductMetricId('退款金额')).toBe('payTimeRefundAmount')
    expect(resolveProductMetricId('退款单数')).toBe('payTimeRefundOrders')
    expect(resolveProductMetricId('refund_cnt')).toBe('refund_cnt')
    expect(productMetricTooltip('refundRelatedOrders')).toContain(
      '不代表违规或风控异常',
    )
    expect(productMetricTooltip('netOrders')).toContain(
      '不由其他订单数相减推算',
    )
    expect(productMetricTooltip('shippedReturnRate')).toContain(
      '不以其他退款率替代',
    )
  })
})
