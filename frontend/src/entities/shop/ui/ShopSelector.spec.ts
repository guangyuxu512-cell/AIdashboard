import { shallowMount } from '@vue/test-utils'
import { ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import { AppSelect } from '@/shared/ui'
import ShopSelector from './ShopSelector.vue'

vi.mock('../api/shop-queries', () => ({
  useShopSelectionOptionsQuery: () => ({
    data: ref([{ label: '测试请求店铺', value: 'shop-1' }]),
    isPending: ref(false),
  }),
}))

describe('ShopSelector clearable opt-in', () => {
  it('keeps required shop selection non-clearable by default', () => {
    const wrapper = shallowMount(ShopSelector, {
      props: { modelValue: 'shop-1' },
    })
    expect(wrapper.findComponent(AppSelect).props('clearable')).toBe(false)
    expect(wrapper.findComponent(AppSelect).props('modelValue')).toBe('shop-1')
  })

  it('forwards explicit clearability and the null update without a fake shop', () => {
    const wrapper = shallowMount(ShopSelector, {
      props: { modelValue: 'shop-1', clearable: true },
    })
    const select = wrapper.findComponent(AppSelect)
    expect(select.props('clearable')).toBe(true)
    select.vm.$emit('update:modelValue', null)
    expect(wrapper.emitted('update:modelValue')).toEqual([[null]])
  })
})
