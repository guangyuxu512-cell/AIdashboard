import { h } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import CompactEntityRow from './CompactEntityRow.vue'
import compactEntityRowSource from './CompactEntityRow.vue?raw'

describe('CompactEntityRow', () => {
  it('renders fixed icon, title, count, status and action slots', () => {
    const wrapper = mount(CompactEntityRow, {
      props: {
        title: '超长实体名称',
        count: 12,
        active: true,
        selectLabel: '选择实体',
      },
      slots: {
        icon: () => h('span', { 'data-slot': 'icon' }, '图标'),
        status: () => h('span', { 'data-slot': 'status' }, '启用'),
        actions: () => h('button', { 'data-slot': 'action' }, '操作'),
      },
    })

    expect(wrapper.classes()).toContain('compact-entity-row--active')
    expect(wrapper.attributes('data-active')).toBe('true')
    expect(
      wrapper.get('.compact-entity-row__select').attributes(),
    ).toMatchObject({
      'aria-label': '选择实体',
      'aria-pressed': 'true',
    })
    expect(wrapper.get('[data-slot="icon"]').text()).toBe('图标')
    expect(wrapper.get('.compact-entity-row__title').text()).toBe(
      '超长实体名称',
    )
    expect(wrapper.get('.compact-entity-row__count').text()).toBe('12')
    expect(wrapper.get('[data-slot="status"]').text()).toBe('启用')
    expect(wrapper.get('[data-slot="action"]').text()).toBe('操作')
    expect(compactEntityRowSource).toMatch(
      /\.compact-entity-row\s*{[^}]*height:\s*var\(--table-list-row-slot-height\);/s,
    )
    expect(compactEntityRowSource).toMatch(
      /\.compact-entity-row__title\s*{[^}]*overflow:\s*hidden;[^}]*text-overflow:\s*ellipsis;[^}]*white-space:\s*nowrap;/s,
    )
  })

  it('emits row selection and isolates action clicks', async () => {
    const action = vi.fn()
    const wrapper = mount(CompactEntityRow, {
      props: { title: '实体', count: 1 },
      slots: {
        actions: () =>
          h('button', { 'data-action': true, onClick: action }, '操作'),
      },
    })

    await wrapper.get('.compact-entity-row__select').trigger('click')
    expect(wrapper.emitted('select')).toEqual([[]])

    await wrapper.get('[data-action]').trigger('click')
    expect(action).toHaveBeenCalledOnce()
    expect(wrapper.emitted('select')).toEqual([[]])
  })

  it('keeps the row selector keyboard focusable', () => {
    const wrapper = mount(CompactEntityRow, {
      attachTo: document.body,
      props: { title: '实体', count: 1 },
    })
    const select = wrapper.get<HTMLButtonElement>('.compact-entity-row__select')

    select.element.focus()
    expect(document.activeElement).toBe(select.element)

    wrapper.unmount()
  })
})
