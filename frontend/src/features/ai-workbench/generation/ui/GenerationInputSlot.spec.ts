import { mount } from '@vue/test-utils'
import { NUpload, NUploadDragger } from 'naive-ui'
import { describe, expect, it } from 'vitest'

import type { GenerationInputSlotDefinition } from '../model/generation-mode-registry'
import type { GenerationSourceImageView } from '../model/types'
import GenerationInputSlot from './GenerationInputSlot.vue'

const definition: GenerationInputSlotDefinition = {
  key: 'PRODUCT_IMAGES',
  label: '商品图片',
  required: true,
  acceptedMaterialRole: 'PRODUCT_SOURCE',
  allowLocalUpload: true,
  allowMaterialLibrary: true,
}

describe('GenerationInputSlot', () => {
  it('uses the library upload control across the whole empty image surface', () => {
    const wrapper = mount(GenerationInputSlot, {
      props: { definition, images: [] },
    })

    expect(wrapper.attributes('data-input-slot')).toBe('PRODUCT_IMAGES')
    expect(wrapper.findComponent(NUpload).props('multiple')).toBe(true)
    expect(wrapper.findComponent(NUploadDragger).exists()).toBe(true)
    expect(wrapper.text()).toContain('点击上传图片')
    expect(
      wrapper.findAll('button').some((button) => button.text() === '上传'),
    ).toBe(false)
  })

  it('emits a local file through the Naive Upload contract', () => {
    const wrapper = mount(GenerationInputSlot, {
      props: { definition, images: [] },
    })
    const file = new File(['image'], '商品图.webp', { type: 'image/webp' })
    const beforeUpload = wrapper
      .findComponent(NUpload)
      .props('onBeforeUpload') as (value: { file: { file: File } }) => boolean

    expect(beforeUpload({ file: { file } })).toBe(false)
    expect(wrapper.emitted('upload')).toEqual([[[file]]])
  })

  it('renders every image and removes only the chosen source', async () => {
    const images: GenerationSourceImageView[] = [1, 2].map((index) => ({
      id: `image-${index}`,
      name: `图片-${index}.webp`,
      previewUrl: `data:image/webp,${index}`,
      role: 'PRODUCT_SOURCE',
      sourceType: 'LOCAL_UPLOAD',
    }))
    const wrapper = mount(GenerationInputSlot, {
      props: { definition, images },
    })

    expect(wrapper.findAll('.generation-input-slot__image')).toHaveLength(2)
    await wrapper.get('[aria-label="移除 图片-1.webp"]').trigger('click')
    expect(wrapper.emitted('remove')).toEqual([['image-1']])
  })
})
