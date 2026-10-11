import { mount, shallowMount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import DataTable from './DataTable.vue'

describe('DataTable', () => {
  it('forwards an opt-in AppTable theme override without changing default tables', () => {
    const props = {
      columns: [{ key: 'name', title: '名称' }],
      data: [{ name: 'A' }],
    }
    const defaultTable = shallowMount(DataTable, { props }).findComponent({
      name: 'AppTable',
    })
    expect(defaultTable.props('themeOverrides')).toBeUndefined()
    const themeOverrides = { tdPaddingMedium: 'var(--space-3)' }
    const customized = shallowMount(DataTable, {
      props: { ...props, themeOverrides },
    }).findComponent({ name: 'AppTable' })
    expect(customized.props('themeOverrides')).toEqual(themeOverrides)
  })
  it('forwards the existing AppTable native sorter without altering default behavior', async () => {
    const wrapper = shallowMount(DataTable, {
      props: {
        columns: [{ key: 'name', title: '名称', sorter: true }],
        data: [{ name: 'A' }],
      },
    })
    const state = { columnKey: 'name', order: 'ascend' }
    wrapper.findComponent({ name: 'AppTable' }).vm.$emit('update:sorter', state)
    expect(wrapper.emitted('update:sorter')).toEqual([[state]])
  })
  it('renders the shared loading state before the first rows arrive', () => {
    const wrapper = mount(DataTable, {
      props: {
        columns: [{ title: '名称', key: 'name' }],
        data: [],
        loading: true,
      },
    })

    expect(wrapper.text()).toContain('正在加载')
  })

  it('renders the shared empty state when there are no rows', () => {
    const wrapper = mount(DataTable, {
      props: {
        columns: [{ title: '名称', key: 'name' }],
        data: [],
        emptyDescription: '没有基础设施记录',
      },
    })

    expect(wrapper.text()).toContain('没有基础设施记录')
  })

  it('renders the shared error state and emits retry', async () => {
    const wrapper = mount(DataTable, {
      props: {
        columns: [{ title: '名称', key: 'name' }],
        error: '请求失败',
      },
    })

    expect(wrapper.text()).toContain('请求失败')
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })

  it('applies the semantic stable viewport only when requested', () => {
    const wrapper = mount(DataTable, {
      props: {
        columns: [{ title: '名称', key: 'name' }],
        data: [],
        viewport: 'stable',
        appearance: 'list',
      },
    })

    expect(wrapper.get('.data-table').classes()).toContain('data-table--stable')
    expect(wrapper.get('.data-table').classes()).toContain(
      'data-table--appearance-list',
    )
  })

  it('supports a flex-fill table body without changing the default mode', () => {
    const wrapper = shallowMount(DataTable, {
      props: {
        columns: [{ title: '名称', key: 'name' }],
        data: [{ name: '测试' }],
        viewport: 'fill',
      },
    })

    expect(wrapper.get('.data-table').classes()).toContain('data-table--fill')
    expect(wrapper.findComponent({ name: 'AppTable' }).props('fill')).toBe(true)
  })
})
