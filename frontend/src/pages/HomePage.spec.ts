import { h } from 'vue'
import { NConfigProvider } from 'naive-ui'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import HomePage from './HomePage.vue'

describe('HomePage', () => {
  it('renders the stage 0B foundation preview', () => {
    const wrapper = mount({
      render: () => h(NConfigProvider, null, { default: () => h(HomePage) }),
    })

    expect(wrapper.text()).toContain('Frontend Design System')
    expect(wrapper.text()).toContain('不包含真实业务')
    expect(wrapper.text()).toContain('Design Token')
    expect(wrapper.text()).toContain('统一状态')
  })
})
