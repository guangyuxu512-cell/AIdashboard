import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import DataTable from './DataTable.vue'

describe('DataTable', () => {
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
})
