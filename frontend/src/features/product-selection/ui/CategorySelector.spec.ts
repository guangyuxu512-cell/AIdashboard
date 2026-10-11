import { mount } from '@vue/test-utils'
import { NCascader } from 'naive-ui'
import { describe, expect, it } from 'vitest'
import type { CategoryNode } from '../model/contracts'
import CategorySelector from './CategorySelector.vue'

const nodes: CategoryNode[] = [
  {
    id: '7',
    name: '行业',
    children: [
      {
        id: '7/1001',
        name: '父类目',
        requestScope: { industryId: '7', categoryIds: ['1001'] },
        children: [
          {
            id: '7/1001/1002',
            name: '三级类目',
            requestScope: { industryId: '7', categoryIds: ['1001', '1002'] },
            children: [
              {
                id: '7/1001/1002/1003',
                name: '四级类目',
                requestScope: {
                  industryId: '7',
                  categoryIds: ['1001', '1002', '1003'],
                },
              },
            ],
          },
        ],
      },
    ],
  },
]

describe('shop-bound category selection', () => {
  it('offers parent-all but emits only the existing real parent path, never a UI wildcard or industry-as-category', async () => {
    const wrapper = mount(CategorySelector, {
      props: { nodes, real: true, modelValue: null },
    })
    const cascader = wrapper.findComponent(NCascader)
    const tree = cascader.props('options')!
    expect(tree[0]!.children![0]!.label).toBe('父类目')
    expect(tree[0]!.children![0]!.children![0]).toEqual({
      value: '7/1001/*',
      label: '全部',
    })
    cascader.vm.$emit('update:value', '7/1001/1002/*')
    expect(wrapper.emitted('update:modelValue')).toEqual([['7/1001/1002']])
    await wrapper.setProps({ modelValue: '7/1001/1002' })
    expect(cascader.props('value')).toBe('7/1001/1002/*')
    cascader.vm.$emit('update:value', '7/1001/1002/1003')
    expect(wrapper.emitted('update:modelValue')![1]).toEqual([
      '7/1001/1002/1003',
    ])
    expect(cascader.props('placement')).toBe('bottom-start')
    expect(cascader.props('menuProps')!.style).toMatchObject({
      overflowX: 'auto',
      pointerEvents: 'auto',
    })
    expect(cascader.props('themeOverrides')).toMatchObject({
      menuHeight: 'var(--select-menu-max-height)',
    })
    wrapper.unmount()
  })
  it('retains Mock parent-all identities and does not reinterpret them as formal platform parameters', () => {
    const wrapper = mount(CategorySelector, {
      props: { nodes, modelValue: null },
    })
    wrapper.findComponent(NCascader).vm.$emit('update:value', '7/1001/*')
    expect(wrapper.emitted('update:modelValue')).toEqual([['7/1001/*']])
    wrapper.unmount()
  })
})
