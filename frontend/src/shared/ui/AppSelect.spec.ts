import { mount, shallowMount } from '@vue/test-utils'
import { NSelect, NTooltip } from 'naive-ui'
import type { SelectProps } from 'naive-ui'
import { h } from 'vue'
import { describe, expect, it, vi } from 'vitest'

import AppSelect from './AppSelect.vue'

describe('AppSelect', () => {
  it('forwards multiple selection and collapsed tag settings', () => {
    const wrapper = shallowMount(AppSelect, {
      props: {
        modelValue: ['one', 'two'],
        options: [
          { label: 'One', value: 'one' },
          { label: 'Two', value: 'two' },
        ],
        multiple: true,
        maxTagCount: 1,
      },
    })

    expect(wrapper.findComponent(NSelect).props()).toMatchObject({
      value: ['one', 'two'],
      multiple: true,
      maxTagCount: 1,
    })

    wrapper.findComponent(NSelect).vm.$emit('update:value', ['one'])
    expect(wrapper.emitted('update:values')).toEqual([[['one']]])
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })

  it('preserves the scalar model update contract', () => {
    const wrapper = shallowMount(AppSelect, {
      props: {
        modelValue: 'one',
        options: [{ label: 'One', value: 'one' }],
      },
    })

    wrapper.findComponent(NSelect).vm.$emit('update:value', 'one')
    expect(wrapper.emitted('update:modelValue')).toEqual([['one']])
    expect(wrapper.emitted('update:values')).toBeUndefined()
  })

  it('can keep a popup inside an existing overlay host', () => {
    const wrapper = shallowMount(AppSelect, {
      props: {
        options: [{ label: 'One', value: 'one' }],
        to: '#app-overlay-host',
      },
    })

    expect(wrapper.findComponent(NSelect).props('to')).toBe('#app-overlay-host')
  })

  it('keeps label tooltips opt-in and custom renderers unchanged by default', () => {
    const renderLabel = vi.fn(() => h('span', 'platform + status'))
    const renderTag = vi.fn(() => h('span', 'custom tag'))
    const wrapper = shallowMount(AppSelect, {
      props: { options: [], renderLabel },
      attrs: { renderTag },
    })
    expect(wrapper.findComponent(NSelect).props('renderLabel')).toBe(
      renderLabel,
    )
    expect(wrapper.findComponent(NSelect).props('renderTag')).toBe(renderTag)
    expect(
      shallowMount(AppSelect, { props: { options: [] } })
        .findComponent(NSelect)
        .props('renderLabel'),
    ).toBeUndefined()
  })

  it('uses full labels for selected text and menu options without treating selected as a context flag', () => {
    const labels = ['A', 'B'].map(
      (suffix) => `同一前缀的长店铺名称及完整业务说明需要悬浮区分-${suffix}`,
    )
    const options = labels.map((label, index) => ({ label, value: index }))
    const wrapper = shallowMount(AppSelect, {
      props: { options, labelTooltip: true, to: '#app-overlay-host' },
    })
    const render = wrapper
      .findComponent(NSelect)
      .props('renderLabel') as NonNullable<SelectProps['renderLabel']>
    for (const option of options) {
      for (const selected of [false, true]) {
        const vnode = render(option as never, selected) as ReturnType<typeof h>
        expect(vnode.type).toBe(NTooltip)
        expect(vnode.props?.to).toBe('#app-overlay-host')
        const slots = vnode.children as {
          default: () => string
          trigger: () => ReturnType<typeof h>
        }
        expect(slots.default()).toBe(option.label)
        expect(slots.trigger().children).toEqual([option.label])
        expect(slots.trigger().props?.style).toMatchObject({
          width: '100%',
          pointerEvents: 'auto',
          whiteSpace: 'nowrap',
          textOverflow: 'ellipsis',
        })
      }
    }
  })

  it('preserves rich and functional labels and the native custom tag precedence', () => {
    const richContent = h(
      'span',
      { class: 'platform-and-status' },
      '平台 · 状态',
    )
    const renderLabel = vi.fn(() => richContent)
    const renderTag = vi.fn(() => h('span', 'native tag'))
    const option = { label: '完整平台与状态名称', value: 'platform' }
    const wrapper = shallowMount(AppSelect, {
      props: {
        options: [option],
        labelTooltip: true,
        renderLabel,
        multiple: true,
        maxTagCount: 1,
      },
      attrs: { renderTag },
    })
    const select = wrapper.findComponent(NSelect)
    const render = select.props('renderLabel') as NonNullable<
      SelectProps['renderLabel']
    >
    const vnode = render(option as never, true) as ReturnType<typeof h>
    expect(
      (vnode.children as { trigger: () => ReturnType<typeof h> }).trigger()
        .children,
    ).toEqual([richContent])
    expect(renderLabel).toHaveBeenCalledWith(option, true)
    expect(select.props()).toMatchObject({
      multiple: true,
      maxTagCount: 1,
      renderTag,
    })
    const functional = { label: vi.fn(() => richContent), value: 'function' }
    const plain = shallowMount(AppSelect, {
      props: { options: [functional], labelTooltip: true },
    })
    const plainRender = plain
      .findComponent(NSelect)
      .props('renderLabel') as NonNullable<SelectProps['renderLabel']>
    expect(plainRender(functional as never, false)).toBe(richContent)
    expect(functional.label).toHaveBeenCalledWith(functional, false)
  })

  it('keeps native multiple tag close callbacks and collapsed tags with opt-in labels', async () => {
    const wrapper = mount(AppSelect, {
      props: {
        modelValue: ['one', 'two'],
        options: [
          { label: '第一项完整名称', value: 'one' },
          { label: '第二项完整名称', value: 'two' },
        ],
        multiple: true,
        maxTagCount: 1,
        labelTooltip: true,
      },
    })
    expect(wrapper.findAll('.n-tag')).toHaveLength(2)
    expect(wrapper.text()).toContain('+1')
    await wrapper.find('.n-tag .n-base-close').trigger('click')
    expect(wrapper.emitted('update:values')).toEqual([[['two']]])
    wrapper.unmount()
  })

  it('does not wrap or intercept a custom tag and respects disabled selection', async () => {
    const wrapper = mount(AppSelect, {
      props: {
        modelValue: ['one'],
        options: [{ label: '长名称', value: 'one' }],
        multiple: true,
        labelTooltip: true,
      },
      attrs: {
        // This test covers tag closure, not the virtual menu (browser tests do).
        show: false,
        renderTag: ({ handleClose }: { handleClose: () => void }) =>
          h('button', { onClick: handleClose }, '自定义标签关闭'),
      },
    })
    expect(wrapper.find('.app-select-label').exists()).toBe(false)
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('update:values')).toEqual([[[]]])
    wrapper.unmount()
    const disabled = mount(AppSelect, {
      props: {
        modelValue: 'one',
        options: [{ label: '不可编辑的长名称', value: 'one' }],
        disabled: true,
        labelTooltip: true,
      },
    })
    expect(disabled.find('.n-base-selection--disabled').exists()).toBe(true)
    await disabled.trigger('click')
    expect(disabled.emitted('update:modelValue')).toBeUndefined()
    expect(disabled.findComponent(NSelect).props('show')).toBeUndefined()
    disabled.unmount()
  })
})
