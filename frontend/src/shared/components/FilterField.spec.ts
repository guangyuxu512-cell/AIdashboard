import { h } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import FilterField from './FilterField.vue'

describe('FilterField', () => {
  it('provides a label and semantic width class around a control', () => {
    const wrapper = mount(FilterField, {
      props: { label: '设备状态', width: 'md' },
      slots: { default: () => h('input', { 'data-test': 'control' }) },
    })

    expect(wrapper.text()).toContain('设备状态')
    expect(wrapper.classes()).toContain('filter-field--md')
    expect(wrapper.get('[data-test="control"]').element).toBeDefined()
  })

  it('supports the compact management pattern without a visible label', () => {
    const wrapper = mount(FilterField, {
      props: { width: 'sm' },
      slots: { default: () => h('input', { 'data-test': 'control' }) },
    })

    expect(wrapper.find('span').exists()).toBe(false)
    expect(wrapper.classes()).not.toContain('filter-field--labelled')
    expect(wrapper.get('[data-test="control"]').element).toBeDefined()
  })
})
