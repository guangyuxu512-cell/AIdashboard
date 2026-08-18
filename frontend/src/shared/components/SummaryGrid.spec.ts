import { h } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import SummaryGrid from './SummaryGrid.vue'

describe('SummaryGrid', () => {
  it('uses a semantic column class and renders summary content', () => {
    const wrapper = mount(SummaryGrid, {
      props: { columns: 3 },
      slots: { default: () => h('article', '统计内容') },
    })

    expect(wrapper.classes()).toContain('summary-grid--3')
    expect(wrapper.text()).toContain('统计内容')
  })
})
