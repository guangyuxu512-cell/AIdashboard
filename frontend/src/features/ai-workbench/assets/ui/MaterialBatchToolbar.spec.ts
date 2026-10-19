import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { AppButton, AppCheckbox } from '@/shared/ui'

import MaterialBatchToolbar from './MaterialBatchToolbar.vue'

describe('MaterialBatchToolbar', () => {
  it('allows global downloads and selection but disables batch deletion', () => {
    const wrapper = mount(MaterialBatchToolbar, {
      props: {
        readOnly: true,
        selectionMode: true,
        selectedCount: 2,
        currentPageCount: 2,
        checked: true,
        indeterminate: false,
      },
    })
    expect(
      wrapper.get('[aria-label="批量删除"]').attributes('disabled'),
    ).toBeDefined()
    expect(
      wrapper.get('[aria-label="批量下载"]').attributes('disabled'),
    ).toBeUndefined()
    expect(wrapper.findComponent(AppCheckbox).props('disabled')).toBe(false)
  })

  it('offers selection and current-page select-all in normal mode', async () => {
    const wrapper = mount(MaterialBatchToolbar, {
      props: {
        selectionMode: false,
        selectedCount: 0,
        currentPageCount: 20,
        checked: false,
        indeterminate: false,
      },
    })
    const checkbox = wrapper.findComponent(AppCheckbox)

    expect(checkbox.props()).toMatchObject({
      modelValue: false,
      indeterminate: false,
      disabled: false,
    })
    expect(wrapper.text()).toContain('选择')
    expect(wrapper.text()).not.toContain('已选')
    expect(wrapper.find('[aria-label="批量下载"]').exists()).toBe(false)
    expect(wrapper.find('[aria-label="批量删除"]').exists()).toBe(false)

    await wrapper.get('[aria-label="选择"]').trigger('click')
    checkbox.vm.$emit('update:modelValue', true)
    expect(wrapper.emitted('start-selection')).toHaveLength(1)
    expect(wrapper.emitted('toggle-all')).toEqual([[true]])
  })

  it('shows compact batch actions and finish only in selection mode', async () => {
    const wrapper = mount(MaterialBatchToolbar, {
      props: {
        selectionMode: true,
        selectedCount: 3,
        currentPageCount: 20,
        checked: false,
        indeterminate: true,
      },
    })
    const checkbox = wrapper.findComponent(AppCheckbox)
    const buttons = wrapper.findAllComponents(AppButton)

    expect(wrapper.text()).toContain('已选 3')
    expect(checkbox.props()).toMatchObject({
      modelValue: false,
      indeterminate: true,
      disabled: false,
    })
    expect(buttons.every((button) => button.props('disabled') === false)).toBe(
      true,
    )

    await wrapper.get('[aria-label="批量下载"]').trigger('click')
    await wrapper.get('[aria-label="批量删除"]').trigger('click')
    await wrapper.get('[aria-label="完成"]').trigger('click')
    expect(wrapper.emitted('download')).toHaveLength(1)
    expect(wrapper.emitted('remove')).toHaveLength(1)
    expect(wrapper.emitted('finish')).toHaveLength(1)
  })
})
