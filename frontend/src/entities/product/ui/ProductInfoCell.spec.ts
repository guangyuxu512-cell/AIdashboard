import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { NMessageProvider } from 'naive-ui'
import { describe, expect, it, vi } from 'vitest'
import ProductInfoCell from './ProductInfoCell.vue'

function render(productId: string | null) {
  return mount(
    defineComponent({
      setup: () => () =>
        h(
          NMessageProvider,
          {},
          {
            default: () =>
              h(ProductInfoCell, {
                productId,
                title: '完整长商品标题',
                imageUrl: null,
              }),
          },
        ),
    }),
  )
}

describe('shared product identity (source b364a89)', () => {
  it.each([
    '12345',
    '123456789012345678',
    '90000000000000000012345678901234567890',
  ])('copies only the complete string ID %s', async (id) => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    })
    const wrapper = render(id)
    expect(wrapper.get('.product-info-cell__id-text').text()).toBe(`ID：${id}`)
    await wrapper.get('.product-info-cell__title').trigger('click')
    await wrapper.get('.product-info-cell__id-text').trigger('click')
    expect(writeText).not.toHaveBeenCalled()
    await wrapper.get('button[aria-label="复制商品ID"]').trigger('click')
    await flushPromises()
    expect(writeText).toHaveBeenCalledExactlyOnceWith(id)
    expect(document.body.textContent).toContain('商品ID已复制')
    wrapper.unmount()
  })
  it.each([null, '', '   '])(
    'does not fabricate or copy a missing ID %s',
    async (id) => {
      const writeText = vi.fn()
      Object.defineProperty(navigator, 'clipboard', {
        configurable: true,
        value: { writeText },
      })
      const wrapper = render(id)
      expect(wrapper.get('.product-info-cell__id-text').text()).toBe('ID：—')
      const button = wrapper.get('button[aria-label="复制商品ID"]')
      expect(button.attributes('disabled')).toBeDefined()
      await button.trigger('click')
      expect(writeText).not.toHaveBeenCalled()
      wrapper.unmount()
    },
  )
  it('guards repeated clicks and offers manual copy when clipboard fails', async () => {
    let fail!: (reason: Error) => void
    const writeText = vi.fn(
      () =>
        new Promise<void>((_, reject) => {
          fail = reject
        }),
    )
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    })
    const wrapper = render('9000000000000000001')
    const button = wrapper.get('button[aria-label="复制商品ID"]')
    await button.trigger('click')
    await button.trigger('click')
    expect(writeText).toHaveBeenCalledTimes(1)
    fail(new Error('controlled clipboard failure'))
    await flushPromises()
    expect(document.body.textContent).toContain(
      '复制失败，可选中商品ID手动复制',
    )
    expect(button.attributes('disabled')).toBeUndefined()
    wrapper.unmount()
  })
})
