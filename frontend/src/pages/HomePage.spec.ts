import { h } from 'vue'
import { NConfigProvider } from 'naive-ui'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import HomePage from './HomePage.vue'

describe('HomePage', () => {
  it('renders the Design System V2 playground', () => {
    const wrapper = mount({
      render: () => h(NConfigProvider, null, { default: () => h(HomePage) }),
    })

    expect(wrapper.text()).toContain('Design System Playground')
    expect(wrapper.text()).toContain('Design Token V2')
    expect(wrapper.text()).toContain('Design Token')
    expect(wrapper.text()).toContain('统一状态')
    expect(wrapper.text()).toContain('Danger')
  })
})
