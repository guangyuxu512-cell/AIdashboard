import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AppButton from './AppButton.vue'

describe('AppButton', () => {
  it('uses the project default size and forwards clicks', async () => {
    const wrapper = mount(AppButton, {
      props: { tone: 'primary' },
      slots: { default: '保存' },
    })

    expect(wrapper.findComponent({ name: 'Button' }).props('size')).toBe(
      'medium',
    )
    await wrapper.trigger('click')
    expect(wrapper.emitted('click')).toHaveLength(1)
  })
  it('opts into token-based links without changing neutral/default buttons', () => {
    const link = mount(AppButton, { props: { tone: 'link', disabled: true } })
    const button = link.findComponent({ name: 'Button' })
    expect(button.props()).toMatchObject({
      type: 'primary',
      text: true,
      quaternary: false,
      disabled: true,
    })
    expect(button.props('themeOverrides')).toMatchObject({
      textColorTextPrimary: 'var(--text-link)',
      textColorTextDisabledPrimary: 'var(--text-disabled)',
    })
    for (const tone of ['secondary', 'text'] as const) {
      const ordinary = mount(AppButton, { props: { tone } }).findComponent({
        name: 'Button',
      })
      expect(ordinary.props('type')).toBe('default')
      expect(ordinary.props('text')).toBe(false)
      expect(ordinary.props('themeOverrides')).toBeUndefined()
      expect(ordinary.props('quaternary')).toBe(tone === 'text')
    }
  })
  it('opts into the existing small button size without changing its tone or default callers', () => {
    const compact = mount(AppButton, {
      props: { size: 'small', tone: 'secondary' },
    }).findComponent({ name: 'Button' })
    expect(compact.props()).toMatchObject({
      size: 'small',
      type: 'default',
      text: false,
      quaternary: false,
    })
    expect(
      mount(AppButton).findComponent({ name: 'Button' }).props('size'),
    ).toBe('medium')
  })
})
