import { describe, expect, it } from 'vitest'
import {
  PRIMARY_PRODUCT_METRICS,
  PRODUCT_METRICS,
  productMetricTooltip,
  resolveProductMetricId,
} from './metrics'
import { normalizeProductColumns } from './column-preferences'
import { PRODUCT_DISPLAY_COLUMNS } from './display-fields'

describe('product metric semantic registry', () => {
  it('does not label every current data source as disconnected and retains the preview warning', () => {
    for (const metric of PRODUCT_METRICS) {
      const tooltip = productMetricTooltip(metric.id)
      expect(tooltip).not.toContain('真实接口尚未接入')
      expect(tooltip).toContain('数据可用性以当前数据源为准')
      expect(tooltip).toContain('演示值不是平台数据')
    }
  })
  it('freezes the seventeen verified source codes and observed raw units without treating legacy ratio IDs as source fields', () => {
    expect(
      PRIMARY_PRODUCT_METRICS.map((metric) => [
        metric.id,
        metric.platformCode,
        metric.rawUnitCode,
      ]),
    ).toEqual([
      ['exposureCount', 'product_show_cnt', 5],
      ['clickCount', 'product_click_cnt', 5],
      ['exposureClickRate', 'product_show_click_converse_uv_rate', 4],
      ['cartUsers', 'click_add_to_cart_uv', 5],
      ['visitCartRate', 'product_add_show_converse_uv_ratio', 4],
      ['netOrders', 'net_pay_cnt', 5],
      ['refundRelatedOrders', 'pay_cnt_exclude_refund', 5],
      ['clickPayRate', 'product_click_pay_converse_uv_rate', 4],
      ['payTimeRefundRate', 'pay_refund_ratio', 4],
      ['pay_amt', 'pay_amt', 3],
      ['pay_cnt', 'pay_cnt', 5],
      ['pay_ucnt', 'pay_ucnt', 5],
      ['payPerOrder', 'per_user_price', 3],
      ['payTimeRefundAmount', 'pay_refund_success_amt', 3],
      ['payTimeRefundOrders', 'pay_refund_success_order_cnt', 5],
      ['product_show_ucnt', 'product_show_ucnt', 5],
      ['product_click_ucnt', 'product_click_ucnt', 5],
    ])
    expect(
      new Set(PRIMARY_PRODUCT_METRICS.map((metric) => metric.platformCode))
        .size,
    ).toBe(17)
    expect(resolveProductMetricId('product_click_show_ucnt_ratio')).toBeNull()
    expect(resolveProductMetricId('product_click_pay_ucnt_ratio')).toBeNull()
    expect(productMetricTooltip('pay_amt')).toContain('金额按原值÷100显示元')
    expect(productMetricTooltip('clickPayRate')).toContain(
      '比例按原值×100显示百分比',
    )
    expect(productMetricTooltip('clickPayRate')).toContain(
      '数据可用性以当前数据源为准',
    )
  })
  it('registers seventeen distinct primary metrics and nineteen Chinese names without duplicate metric records', () => {
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
    ).toEqual(['exposureClickRate', 'clickPayRate'])
    for (const metric of PRODUCT_METRICS)
      expect(productMetricTooltip(metric.id)).toContain(metric.officialLabel)
  })
  it('preserves old refund, settlement and unverified stock IDs rather than rebinding their meaning', () => {
    expect(resolveProductMetricId('refund_amt')).toBe('refund_amt')
    expect(resolveProductMetricId('refund_cnt')).toBe('refund_cnt')
    expect(resolveProductMetricId('receive_amt')).toBe('receive_amt')
    expect(resolveProductMetricId('stock_cnt')).toBe('stock_cnt')
    expect(PRODUCT_DISPLAY_COLUMNS.map(({ id }) => id)).not.toEqual(
      expect.arrayContaining([
        'refund_amt',
        'refund_cnt',
        'receive_amt',
        'stock_cnt',
      ]),
    )
    expect(resolveProductMetricId('退款金额')).toBe('payTimeRefundAmount')
    expect(resolveProductMetricId('退款单数')).toBe('payTimeRefundOrders')
    expect(resolveProductMetricId('refund_cnt')).toBe('refund_cnt')
    expect(productMetricTooltip('refundRelatedOrders')).toContain(
      '不代表违规或风控异常',
    )
    expect(productMetricTooltip('refundRelatedOrders')).toContain(
      '不等同发生退款订单数',
    )
    expect(productMetricTooltip('refundRelatedOrders')).toContain(
      '具体业务定义待确认',
    )
    expect(productMetricTooltip('netOrders')).toContain(
      '不由其他订单数相减推算',
    )
    expect(productMetricTooltip('payTimeRefundRate')).toContain(
      '不自行相加两阶段百分比',
    )
  })
  it('uses the total payment-time refund rate as a distinct semantic metric, not a shipped-return alias', () => {
    const definition = PRIMARY_PRODUCT_METRICS.find(
      (metric) => metric.id === 'payTimeRefundRate',
    )!
    expect(definition).toMatchObject({
      label: '退款率',
      officialLabel: '退款率（支付时间）',
      format: 'ratio',
    })
    expect(resolveProductMetricId('shippedReturnRate')).toBeNull()
    expect(resolveProductMetricId('退货率')).toBeNull()
    expect(resolveProductMetricId('退款率')).toBe('payTimeRefundRate')
    expect(productMetricTooltip('payTimeRefundRate')).toContain(
      '包含发货前与发货后',
    )
    expect(productMetricTooltip('payTimeRefundRate')).toContain(
      '不以仅发货后或退款时间口径替代',
    )
  })
})
