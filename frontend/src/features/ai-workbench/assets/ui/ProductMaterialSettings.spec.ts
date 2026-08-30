import { shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import type { ProductMaterialGroup } from '../model/types'
import AppSelect from '@/shared/ui/AppSelect.vue'
import AppSwitch from '@/shared/ui/AppSwitch.vue'

import ProductMaterialSettings from './ProductMaterialSettings.vue'

function createProduct(
  overrides: Partial<ProductMaterialGroup> = {},
): ProductMaterialGroup {
  return {
    id: 'product-1',
    name: '手机支架',
    enabled: true,
    normalGenerationEnabled: true,
    normalTemplateGroupIds: ['normal-standard-set', 'normal-lifestyle-set'],
    styleReplicationEnabled: true,
    styleReplicationTemplateGroupIds: [
      'style-competitor-a',
      'style-scene-replication',
    ],
    createdAt: '2026-08-31T00:00:00.000Z',
    updatedAt: '2026-08-31T00:00:00.000Z',
    assets: [],
    ...overrides,
  }
}

function mountSettings(overrides: Partial<ProductMaterialGroup> = {}) {
  return shallowMount(ProductMaterialSettings, {
    props: { product: createProduct(overrides) },
  })
}

describe('ProductMaterialSettings', () => {
  it('uses compact multiple selects and filters options by generation mode', () => {
    const wrapper = mountSettings()
    const [normalSelect, styleSelect] = wrapper.findAllComponents(AppSelect)
    const normalLabels = normalSelect!
      .props('options')
      .map((option) => option.label)
    const styleLabels = styleSelect!
      .props('options')
      .map((option) => option.label)

    expect(normalLabels).toEqual([
      '电商标准套图 A',
      '极简主图组',
      '生活场景套图',
      '新品详情套图',
    ])
    expect(styleLabels).toEqual(['竞品复刻 A', '极简风格复刻', '场景复刻组'])
    expect(normalLabels).not.toContain('竞品复刻 A')
    expect(styleLabels).not.toContain('电商标准套图 A')
    expect(normalSelect!.props()).toMatchObject({
      multiple: true,
      maxTagCount: 1,
      clearable: true,
      placeholder: '未绑定',
    })
    expect(styleSelect!.props()).toMatchObject({
      multiple: true,
      maxTagCount: 1,
      clearable: true,
      placeholder: '未绑定',
    })
  })

  it('emits independent template ID array updates', () => {
    const wrapper = mountSettings()
    const [normalSelect, styleSelect] = wrapper.findAllComponents(AppSelect)

    normalSelect!.vm.$emit('update:values', [
      'normal-standard-set',
      'normal-minimal-main',
    ])
    expect(wrapper.emitted('update:normalTemplateGroupIds')).toEqual([
      [['normal-standard-set', 'normal-minimal-main']],
    ])
    expect(
      wrapper.emitted('update:styleReplicationTemplateGroupIds'),
    ).toBeUndefined()

    styleSelect!.vm.$emit('update:values', [
      'style-competitor-a',
      'style-minimal-replication',
    ])
    expect(wrapper.emitted('update:styleReplicationTemplateGroupIds')).toEqual([
      [['style-competitor-a', 'style-minimal-replication']],
    ])

    normalSelect!.vm.$emit('update:values', [])
    expect(wrapper.emitted('update:normalTemplateGroupIds')?.at(-1)).toEqual([
      [],
    ])
  })

  it('disables mode controls without clearing selected arrays', async () => {
    const wrapper = mountSettings()
    const switches = wrapper.findAllComponents(AppSwitch)
    const [normalSelect, styleSelect] = wrapper.findAllComponents(AppSelect)
    const normalIds = ['normal-standard-set', 'normal-lifestyle-set']
    const styleIds = ['style-competitor-a', 'style-scene-replication']

    switches[1]!.vm.$emit('update:modelValue', false)
    expect(wrapper.emitted('update:normalGenerationEnabled')).toEqual([[false]])
    expect(wrapper.emitted('update:normalTemplateGroupIds')).toBeUndefined()

    await wrapper.setProps({
      product: createProduct({
        normalGenerationEnabled: false,
        styleReplicationEnabled: false,
      }),
    })
    expect(normalSelect!.props('disabled')).toBe(true)
    expect(styleSelect!.props('disabled')).toBe(true)
    expect(normalSelect!.props('modelValue')).toEqual(normalIds)
    expect(styleSelect!.props('modelValue')).toEqual(styleIds)

    await wrapper.setProps({ product: createProduct({ enabled: false }) })
    expect(switches[1]!.props('disabled')).toBe(true)
    expect(switches[2]!.props('disabled')).toBe(true)
    expect(normalSelect!.props('modelValue')).toEqual(normalIds)
    expect(styleSelect!.props('modelValue')).toEqual(styleIds)

    await wrapper.setProps({ product: createProduct() })
    expect(normalSelect!.props('disabled')).toBe(false)
    expect(styleSelect!.props('disabled')).toBe(false)
    expect(normalSelect!.props('modelValue')).toEqual(normalIds)
    expect(styleSelect!.props('modelValue')).toEqual(styleIds)
  })

  it('renders each product binding including explicit empty arrays', async () => {
    const wrapper = mountSettings()
    const [normalSelect, styleSelect] = wrapper.findAllComponents(AppSelect)

    await wrapper.setProps({
      product: createProduct({
        id: 'product-2',
        name: '马克杯',
        normalTemplateGroupIds: ['normal-minimal-main'],
        styleReplicationEnabled: false,
        styleReplicationTemplateGroupIds: ['style-minimal-replication'],
      }),
    })
    expect(normalSelect!.props('modelValue')).toEqual(['normal-minimal-main'])
    expect(styleSelect!.props('modelValue')).toEqual([
      'style-minimal-replication',
    ])
    expect(styleSelect!.props('disabled')).toBe(true)

    await wrapper.setProps({
      product: createProduct({
        id: 'product-3',
        normalTemplateGroupIds: [],
        styleReplicationTemplateGroupIds: [],
      }),
    })
    expect(normalSelect!.props('modelValue')).toEqual([])
    expect(styleSelect!.props('modelValue')).toEqual([])
  })
})
