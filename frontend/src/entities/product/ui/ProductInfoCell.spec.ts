import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { NEllipsis, NImage, NMessageProvider } from 'naive-ui'
import { describe, expect, it, vi } from 'vitest'
import ProductInfoCell from './ProductInfoCell.vue'
import ProductImage from './ProductImage.vue'
import ExternalProductImage from '@/features/product-selection/ui/ExternalProductImage.vue'

describe('shared product display', () => {
  it('copies the complete string ID and keeps the title and manually selectable ID visible', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    })
    const id = '900000000000000000123'
    const wrapper = mount(
      defineComponent({
        setup: () => () =>
          h(
            NMessageProvider,
            {},
            {
              default: () =>
                h(ProductInfoCell, {
                  productId: id,
                  title: '完整长商品名称',
                  imageUrl: null,
                }),
            },
          ),
      }),
    )
    await wrapper.get('button[aria-label="复制商品ID"]').trigger('click')
    await flushPromises()
    expect(writeText).toHaveBeenCalledWith(id)
    expect(wrapper.get('.product-info-cell__id span').text()).toBe('ID：' + id)
    expect(wrapper.text()).toContain('完整长商品名称')
    expect(wrapper.findComponent(NEllipsis).props('lineClamp')).toBeUndefined()
    expect(wrapper.findComponent(NEllipsis).props('tooltip')).toBe(true)
    const idEllipsis = wrapper.findAllComponents(NEllipsis)[1]!
    expect(idEllipsis.props('lineClamp')).toBeUndefined()
    expect(idEllipsis.props('tooltip')).toMatchObject({
      placement: 'top-start',
      contentStyle: { overflowWrap: 'anywhere' },
    })
    wrapper.unmount()
  })
  it('preserves candidate image dimensions, no-referrer, retry and source reset through the compatibility facade', async () => {
    const wrapper = mount(ExternalProductImage, {
      props: { src: '/test.webp', title: '商品', size: 'thumbnail' },
    })
    expect(wrapper.findComponent(ProductImage).props('size')).toBe('thumbnail')
    expect(wrapper.find('.product-image--thumbnail').exists()).toBe(true)
    expect(wrapper.findComponent(NImage).props('imgProps')).toMatchObject({
      loading: 'lazy',
      referrerpolicy: 'no-referrer',
    })
    wrapper.findComponent(NImage).vm.$emit('error')
    await flushPromises()
    await wrapper.get('button').trigger('click')
    expect(wrapper.findComponent(NImage).exists()).toBe(true)
    wrapper.findComponent(NImage).vm.$emit('error')
    await wrapper.setProps({ src: '/next.webp' })
    expect(wrapper.findComponent(NImage).props('src')).toBe('/next.webp')
    wrapper.unmount()
  })
})
