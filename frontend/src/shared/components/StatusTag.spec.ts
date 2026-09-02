import { shallowMount } from '@vue/test-utils'
import { NTag } from 'naive-ui'
import { describe, expect, it } from 'vitest'

import StatusTag from './StatusTag.vue'

describe('StatusTag', () => {
  it('keeps the standard tag appearance by default', () => {
    const wrapper = shallowMount(StatusTag, {
      props: { label: '成功', tone: 'success' },
    })

    expect(wrapper.findComponent(NTag).exists()).toBe(true)
  })

  it('provides a compact accessible status indicator', () => {
    const wrapper = shallowMount(StatusTag, {
      props: { label: '启用', tone: 'success', appearance: 'dot' },
    })
    const indicator = wrapper.get('.status-tag__dot')

    expect(wrapper.findComponent(NTag).exists()).toBe(false)
    expect(indicator.classes()).toContain('status-tag__dot--success')
    expect(indicator.attributes()).toMatchObject({
      'aria-label': '启用',
      role: 'status',
    })
  })
})
