import { mount } from '@vue/test-utils'
import { NImage } from 'naive-ui'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import ProductImage from './ProductImage.vue'

describe('ProductImage explicit compact thumbnail', () => {
  beforeAll(() =>
    document.documentElement.style.setProperty(
      '--list-compact-control-height',
      '28px',
    ),
  )
  afterAll(() =>
    document.documentElement.style.removeProperty(
      '--list-compact-control-height',
    ),
  )
  it('keeps summary as the default even when a consumer passes compact', () => {
    const wrapper = mount(ProductImage, {
      props: { src: null, title: '商品', density: 'compact' },
    })
    expect(wrapper.classes()).toContain('product-image--summary')
    expect(wrapper.classes()).not.toContain('product-image--compact')
    expect(wrapper.text()).toBe('—')
    wrapper.unmount()
  })

  it('uses the same compact image slot for missing, loading, failure and retry', async () => {
    const wrapper = mount(ProductImage, {
      props: {
        src: null,
        title: '商品',
        size: 'thumbnail',
        density: 'compact',
      },
    })
    expect(wrapper.classes()).toContain('product-image--compact')
    expect(wrapper.findComponent(NImage).exists()).toBe(false)
    await wrapper.setProps({ src: '/fixture.webp' })
    expect(wrapper.findComponent(NImage).props()).toMatchObject({
      objectFit: 'contain',
      previewDisabled: false,
      imgProps: { loading: 'lazy', referrerpolicy: 'no-referrer' },
    })
    wrapper.findComponent(NImage).vm.$emit('error')
    await wrapper.vm.$nextTick()
    expect(wrapper.classes()).toContain('product-image--compact')
    await wrapper.get('button[aria-label="重试商品图片"]').trigger('click')
    expect(wrapper.findComponent(NImage).exists()).toBe(true)
    await wrapper.setProps({ density: 'default' })
    expect(wrapper.classes()).not.toContain('product-image--compact')
    wrapper.unmount()
  })
})
