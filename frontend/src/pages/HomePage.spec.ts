import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import HomePage from './HomePage.vue'

describe('HomePage', () => {
  it('renders the stage placeholder', () => {
    const wrapper = mount(HomePage)

    expect(wrapper.text()).toContain('阶段 0A 工程骨架已就绪。')
  })
})
