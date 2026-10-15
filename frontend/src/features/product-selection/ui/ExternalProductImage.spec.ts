import { flushPromises, mount } from '@vue/test-utils'
import { NImage } from 'naive-ui'
import { describe, expect, it } from 'vitest'
import { ProductImage } from '@/entities/product'
import ExternalProductImage from './ExternalProductImage.vue'

describe('existing image facade', () => {
  it('retains thumbnail, no-referrer, preview, failure retry and source reset', async () => {
    const wrapper = mount(ExternalProductImage, {
      props: { src: '/test.webp', title: '商品', size: 'thumbnail' },
    })
    expect(wrapper.findComponent(ProductImage).props('size')).toBe('thumbnail')
    const image = wrapper.findComponent(NImage)
    expect(image.props()).toMatchObject({
      objectFit: 'contain',
      previewDisabled: false,
      imgProps: { loading: 'lazy', referrerpolicy: 'no-referrer' },
    })
    expect(image.props('imgProps')).not.toHaveProperty('crossorigin')
    image.vm.$emit('error')
    await flushPromises()
    await wrapper.get('button[aria-label="重试商品图片"]').trigger('click')
    expect(wrapper.findComponent(NImage).exists()).toBe(true)
    wrapper.findComponent(NImage).vm.$emit('error')
    await wrapper.setProps({ src: '/next.webp' })
    expect(wrapper.findComponent(NImage).props('src')).toBe('/next.webp')
    wrapper.unmount()
  })
  it('keeps missing image and default summary size without sending an image request', () => {
    const wrapper = mount(ExternalProductImage, {
      props: { src: null, title: '商品' },
    })
    expect(wrapper.findComponent(ProductImage).props('size')).toBe('summary')
    expect(wrapper.findComponent(NImage).exists()).toBe(false)
    expect(wrapper.text()).toBe('—')
    wrapper.unmount()
  })
})
