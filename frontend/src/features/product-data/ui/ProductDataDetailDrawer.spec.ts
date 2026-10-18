import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { NDescriptions } from 'naive-ui'
import { describe, expect, it } from 'vitest'
import { createMockProductDataSource } from '../api/product-data-mock'
import { emptyProductFilters } from '../model/query'
import ProductDataDetailDrawer from './ProductDataDetailDrawer.vue'

const DrawerStub = defineComponent({
  props: ['show', 'title'],
  emits: ['update:show'],
  template: '<aside v-if="show"><slot /><slot name="footer" /></aside>',
})
const TooltipStub = defineComponent({
  template: '<span><slot name="trigger" /></span>',
})

describe('product data detail display whitelist', () => {
  it('uses the same four fixed groups, including view aliases but excluding retired fields', async () => {
    const row = (
      await createMockProductDataSource().list({
        filters: emptyProductFilters(),
        period: { startDate: '2026-10-01', endDate: '2026-10-01' },
        page: 1,
        pageSize: 20,
        sort: null,
      })
    ).items[0]!
    const wrapper = mount(ProductDataDetailDrawer, {
      props: { show: true, row },
      global: {
        stubs: {
          DetailDrawer: DrawerStub,
          NTooltip: TooltipStub,
          ProductInfoCell: true,
        },
      },
    })
    try {
      const groups = wrapper.findAll('.product-data-detail__group')
      expect(groups).toHaveLength(4)
      expect(groups.map((group) => group.find('h3').text())).toEqual([
        '基础字段',
        '核心指标',
        '交易指标',
        '流量指标',
      ])
      expect(groups[0]!.text()).toContain('店铺')
      for (const label of [
        '曝光',
        '点击量',
        '点击率',
        '加购量',
        '加购率',
        '真实订单',
        '异常订单',
        '转化率',
        '退款率',
      ])
        expect(groups[1]!.text()).toContain(label)
      for (const label of [
        '支付金额',
        '订单数',
        '成交人数',
        '客单价',
        '退款金额',
        '退款单数',
      ])
        expect(groups[2]!.text()).toContain(label)
      for (const label of ['曝光人数', '点击人数', '曝光点击率', '点击成交率'])
        expect(groups[3]!.text()).toContain(label)
      expect(wrapper.findAllComponents(NDescriptions)).toHaveLength(4)
      expect(wrapper.text()).not.toContain('结算金额')
      expect(wrapper.text()).not.toContain('退款金额（退款时间）')
      expect(wrapper.text()).not.toContain('实时可售库存')
      expect(wrapper.text()).not.toContain('商品分组')
      expect(wrapper.text()).not.toContain('统计日期')
      expect(wrapper.text()).not.toContain('数据时间')
    } finally {
      wrapper.unmount()
    }
  })
})
