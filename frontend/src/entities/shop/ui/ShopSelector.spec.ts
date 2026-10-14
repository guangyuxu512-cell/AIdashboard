import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { AppSelect } from '@/shared/ui'
import ShopSelector from './ShopSelector.vue'

vi.mock('../api/shop-queries', () => ({
  useShopSelectionOptionsQuery: () => ({
    data: ref([{ label: '店铺A', value: 'shop-a' }]),
    isPending: ref(false),
  }),
}))

describe('ShopSelector optional clear action', () => {
  it('preserves the non-clearable default for existing required-shop forms', () => {
    const wrapper = mount(ShopSelector, { props: { modelValue: 'shop-a' } })
    expect(wrapper.findComponent(AppSelect).props('clearable')).toBe(false)
    expect(wrapper.findComponent(AppSelect).props('options')).toEqual([
      { label: '店铺A', value: 'shop-a' },
    ])
    wrapper.unmount()
  })
  it('opts in to the existing clearable Select and emits null without choosing another shop', () => {
    const wrapper = mount(ShopSelector, {
      props: { modelValue: 'shop-a', clearable: true },
    })
    const select = wrapper.findComponent(AppSelect)
    expect(select.props('clearable')).toBe(true)
    select.vm.$emit('update:modelValue', null)
    expect(wrapper.emitted('update:modelValue')).toEqual([[null]])
    wrapper.unmount()
  })
})
