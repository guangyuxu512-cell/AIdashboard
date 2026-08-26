import { createPinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it } from 'vitest'

import { useThemeStore } from '@/app/stores/theme'
import FoundationPage from '@/pages/FoundationPage.vue'

describe('FoundationPage', () => {
  afterEach(() => {
    document.body.innerHTML = ''
    window.localStorage.clear()
  })

  it('renders the Vant foundation controls and opens the bottom sheet', async () => {
    const pinia = createPinia()
    const wrapper = mount(FoundationPage, {
      attachTo: document.body,
      global: {
        plugins: [pinia],
        stubs: {
          teleport: true,
          transition: false,
        },
      },
    })

    await wrapper.get('input').setValue('验证内容')
    expect((wrapper.get('input').element as HTMLInputElement).value).toBe(
      '验证内容',
    )

    await wrapper.get('[data-testid="open-foundation-sheet"]').trigger('click')
    expect(wrapper.text()).toContain('底部面板')

    const darkButton = wrapper
      .findAll('button')
      .find((button) => button.text() === '深色')
    expect(darkButton).toBeDefined()
    await darkButton?.trigger('click')
    expect(useThemeStore(pinia).mode).toBe('dark')

    wrapper.unmount()
  })
})
