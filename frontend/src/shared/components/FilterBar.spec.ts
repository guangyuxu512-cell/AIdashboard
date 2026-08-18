import { h } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import FilterBar from './FilterBar.vue'

describe('FilterBar', () => {
  it('keeps filter actions and the primary action in one toolbar', () => {
    const wrapper = mount(FilterBar, {
      slots: {
        default: () => h('input', { placeholder: '搜索' }),
        actions: () => h('button', '查询'),
        'primary-action': () => h('button', '新增'),
      },
    })

    expect(wrapper.get('.filter-bar__toolbar').text()).toContain('查询')
    expect(wrapper.get('.filter-bar__primary-action').text()).toBe('新增')
    expect(wrapper.findAll('section')).toHaveLength(1)
  })
})
