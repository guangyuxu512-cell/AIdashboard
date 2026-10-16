import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { AppNumberInput, AppSelect } from '@/shared/ui'
import ProductMetricRangeField from './ProductMetricRangeField.vue'

describe('product metric range control', () => {
  it('only exposes manual bounds for custom, preserves one-sided drafts and clears back to unlimited', async () => {
    const wrapper = mount(ProductMetricRangeField, {
      props: {
        metricId: 'exposureCount',
        modelValue: { choice: 'unlimited', min: null, max: null },
        disabled: false,
      },
    })
    expect(wrapper.findAllComponents(AppNumberInput)).toHaveLength(0)
    wrapper.findComponent(AppSelect).vm.$emit('update:modelValue', 'preset-2')
    expect(wrapper.emitted('update:modelValue')!.at(-1)).toEqual([
      { choice: 'preset-2', min: null, max: null },
    ])
    await wrapper.setProps({
      modelValue: { choice: 'custom', min: null, max: null },
    })
    const inputs = wrapper.findAllComponents(AppNumberInput)
    expect(inputs).toHaveLength(2)
    inputs[0]!.vm.$emit('update:modelValue', 25)
    expect(wrapper.emitted('update:modelValue')!.at(-1)).toEqual([
      { choice: 'custom', min: 25, max: null },
    ])
    expect(wrapper.props('modelValue').min).toBeNull()
    wrapper.findComponent(AppSelect).vm.$emit('update:modelValue', null)
    expect(wrapper.emitted('update:modelValue')!.at(-1)).toEqual([
      { choice: 'unlimited', min: null, max: null },
    ])
    await wrapper.setProps({ disabled: true, error: '上限必须大于下限' })
    expect(wrapper.findComponent(AppSelect).props('disabled')).toBe(true)
    expect(
      wrapper
        .findAllComponents(AppNumberInput)
        .every((input) => input.props('disabled')),
    ).toBe(true)
    expect(wrapper.get('[role="alert"]').text()).toContain('上限必须大于下限')
    wrapper.unmount()
  })
})
