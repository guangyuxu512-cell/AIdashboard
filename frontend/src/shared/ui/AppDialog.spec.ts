import { mount } from '@vue/test-utils'
import { NModal } from 'naive-ui'
import { describe, expect, it } from 'vitest'

import AppDialog from './AppDialog.vue'

describe('AppDialog', () => {
  it('constrains the card to the viewport and delegates scrolling to its body', () => {
    const wrapper = mount(AppDialog, {
      props: {
        show: false,
        title: '参数配置',
      },
    })

    const modal = wrapper.findComponent(NModal)

    expect(modal.props('contentScrollable')).toBe(true)
    expect(modal.vm.$attrs.style).toMatchObject({
      maxHeight: 'var(--dialog-max-height)',
    })
    expect(modal.vm.$attrs.class).toContain('app-dialog')
  })
})
