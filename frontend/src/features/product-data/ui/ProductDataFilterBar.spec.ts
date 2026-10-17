import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'
import { AppButton, AppSelect } from '@/shared/ui'
import { emptyProductFilters } from '../model/query'
import ProductDataFilterBar from './ProductDataFilterBar.vue'
import ProductMetricRangeField from './ProductMetricRangeField.vue'

vi.mock('@/entities/shop/api/shop-queries', () => ({
  useShopSelectionOptionsQuery: () => ({
    data: ref([]),
    isFetching: ref(false),
  }),
}))

let previousHeight = ''
beforeAll(() => {
  previousHeight = document.documentElement.style.getPropertyValue(
    '--list-compact-control-height',
  )
  document.documentElement.style.setProperty(
    '--list-compact-control-height',
    '28px',
  )
})
afterAll(() => {
  if (previousHeight)
    document.documentElement.style.setProperty(
      '--list-compact-control-height',
      previousHeight,
    )
  else
    document.documentElement.style.removeProperty(
      '--list-compact-control-height',
    )
})

describe('Product Data verified Real range controls', () => {
  it('opens all nine ranges without enabling unproved group, sale or carrier dimensions', async () => {
    const wrapper = mount(ProductDataFilterBar, {
      props: {
        modelValue: emptyProductFilters(),
        groups: [],
        enabled: true,
        loading: false,
        nativeOnly: true,
      },
      global: { stubs: { ProductMetricRangeField: true } },
    })
    try {
      const more = wrapper
        .findAllComponents(AppButton)
        .find((button) => button.text() === '更多筛选')!
      await more.trigger('click')
      const fields = wrapper.findAllComponents(ProductMetricRangeField)
      expect(fields).toHaveLength(9)
      expect(fields.map((field) => field.props('metricId'))).toEqual([
        'exposureCount',
        'clickCount',
        'exposureClickRate',
        'cartUsers',
        'visitCartRate',
        'netOrders',
        'refundRelatedOrders',
        'clickPayRate',
        'payTimeRefundRate',
      ])
      expect(fields.every((field) => field.props('disabled') === false)).toBe(
        true,
      )
      const selects = wrapper.findAllComponents(AppSelect)
      for (const placeholder of ['商品分组', '基准售卖切片', '基准载体切片'])
        expect(
          selects
            .find((select) => select.props('placeholder') === placeholder)
            ?.props('disabled'),
        ).toBe(true)
      expect(wrapper.text()).not.toContain('区间含下限')
      expect(wrapper.text()).not.toContain('百分比填 1 表示 1%')
      await more.trigger('click')
      expect(wrapper.findAllComponents(ProductMetricRangeField)).toHaveLength(0)
      expect(more.attributes('aria-expanded')).toBe('false')
      await more.trigger('click')
      expect(wrapper.findAllComponents(ProductMetricRangeField)).toHaveLength(9)
      await wrapper.setProps({ enabled: false })
      expect(
        wrapper
          .findAllComponents(ProductMetricRangeField)
          .every((field) => field.props('disabled') === true),
      ).toBe(true)
    } finally {
      wrapper.unmount()
    }
  })
})
