import { describe, expect, it } from 'vitest'
import {
  DEFAULT_PRODUCT_COLUMNS,
  PRODUCT_DATA_FIELD_GROUPS,
  PRODUCT_DISPLAY_COLUMNS,
  orderProductDisplayColumns,
  productDisplayMetricId,
} from './display-fields'

describe('product data display whitelist', () => {
  it('freezes the approved groups, field order and new-user default', () => {
    expect(PRODUCT_DATA_FIELD_GROUPS).toEqual([
      { id: 'basic', label: '基础字段' },
      { id: 'core', label: '核心指标' },
      { id: 'transaction', label: '交易指标' },
      { id: 'traffic', label: '流量指标' },
    ])
    expect(
      PRODUCT_DISPLAY_COLUMNS.map(({ id, label, group }) => [id, label, group]),
    ).toEqual([
      ['shop', '店铺', 'basic'],
      ['exposureCount', '曝光', 'core'],
      ['clickCount', '点击量', 'core'],
      ['exposureClickRate', '点击率', 'core'],
      ['cartUsers', '加购量', 'core'],
      ['visitCartRate', '加购率', 'core'],
      ['netOrders', '真实订单', 'core'],
      ['refundRelatedOrders', '异常订单', 'core'],
      ['clickPayRate', '转化率', 'core'],
      ['payTimeRefundRate', '退款率', 'core'],
      ['pay_amt', '支付金额', 'transaction'],
      ['pay_cnt', '订单数', 'transaction'],
      ['pay_ucnt', '成交人数', 'transaction'],
      ['payPerOrder', '客单价', 'transaction'],
      ['payTimeRefundAmount', '退款金额', 'transaction'],
      ['payTimeRefundOrders', '退款单数', 'transaction'],
      ['product_show_ucnt', '曝光人数', 'traffic'],
      ['product_click_ucnt', '点击人数', 'traffic'],
      ['trafficExposureClickRate', '曝光点击率', 'traffic'],
      ['trafficClickPayRate', '点击成交率', 'traffic'],
    ])
    expect(DEFAULT_PRODUCT_COLUMNS).toEqual(
      PRODUCT_DISPLAY_COLUMNS.filter(
        ({ group }) => group === 'basic' || group === 'core',
      ).map(({ id }) => id),
    )
  })

  it('reuses the two existing ratio metrics for traffic aliases and excludes unapproved placeholders', () => {
    expect(productDisplayMetricId('trafficExposureClickRate')).toBe(
      'exposureClickRate',
    )
    expect(productDisplayMetricId('trafficClickPayRate')).toBe('clickPayRate')
    const ids = PRODUCT_DISPLAY_COLUMNS.map(({ id }) => id)
    expect(ids).not.toEqual(
      expect.arrayContaining([
        'receive_amt',
        'refund_amt',
        'refund_cnt',
        'stock_cnt',
        'group',
        'selling',
        'carrier',
        'updatedAt',
      ]),
    )
  })

  it('always restores fixed business order instead of checkbox or stored order', () => {
    expect(
      orderProductDisplayColumns([
        'trafficClickPayRate',
        'pay_amt',
        'shop',
        'clickCount',
      ]),
    ).toEqual(['shop', 'clickCount', 'pay_amt', 'trafficClickPayRate'])
  })
})
