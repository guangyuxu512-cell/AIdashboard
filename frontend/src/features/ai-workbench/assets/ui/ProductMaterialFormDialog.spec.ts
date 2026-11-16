import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { defineComponent } from 'vue'

import type { ProductMaterialGroup } from '../model/types'
import { AppInput } from '@/shared/ui'

import ProductMaterialFormDialog from './ProductMaterialFormDialog.vue'

const AppDialogStub = defineComponent({
  name: 'AppDialog',
  emits: ['confirm'],
  template: '<div><slot /></div>',
})

function mountDialog(
  props: InstanceType<typeof ProductMaterialFormDialog>['$props'],
) {
  return mount(ProductMaterialFormDialog, {
    props,
    global: { stubs: { AppDialog: AppDialogStub } },
  })
}

function createProduct(): ProductMaterialGroup {
  return {
    id: 'product-1',
    name: '手机支架',
    enabled: true,
    normalGenerationEnabled: true,
    normalTemplateGroupIds: [],
    styleReplicationEnabled: true,
    styleReplicationTemplateGroupIds: [],
    createdAt: '2026-08-31T00:00:00.000Z',
    updatedAt: '2026-08-31T00:00:00.000Z',
    assets: [],
  }
}

describe('ProductMaterialFormDialog', () => {
  it('creates a product folder with one name field', async () => {
    const wrapper = mountDialog({ show: true, mode: 'create', product: null })

    expect(wrapper.findAllComponents(AppInput)).toHaveLength(1)
    expect(wrapper.findComponent(AppInput).props('placeholder')).toBe(
      '请输入产品名称',
    )

    wrapper
      .findComponent(AppInput)
      .vm.$emit('update:modelValue', '桌面灯素材文件夹')
    wrapper.getComponent({ name: 'AppDialog' }).vm.$emit('confirm')
    await flushPromises()

    expect(wrapper.emitted('save')).toEqual([[{ name: '桌面灯素材文件夹' }]])
  })

  it('renames only the product folder name', async () => {
    const wrapper = mountDialog({
      show: false,
      mode: 'rename',
      product: createProduct(),
    })
    await wrapper.setProps({ show: true })
    await flushPromises()

    expect(wrapper.findAllComponents(AppInput)).toHaveLength(1)
    expect(wrapper.findComponent(AppInput).props('modelValue')).toBe('手机支架')
  })
})
