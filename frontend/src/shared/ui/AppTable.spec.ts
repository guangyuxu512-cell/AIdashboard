import { shallowMount } from '@vue/test-utils'
import { NDataTable } from 'naive-ui'
import { describe, expect, it } from 'vitest'
import AppTable from './AppTable.vue'

describe('AppTable shared column dividers', () => {
  it.each(['grid', 'list'] as const)(
    'uses native vertical dividers for %s without changing table behavior',
    (appearance) => {
      const wrapper = shallowMount(AppTable, {
        props: {
          appearance,
          columns: [
            { type: 'selection', fixed: 'left' },
            { title: '名称', key: 'name', sorter: true },
            { title: '操作', key: 'action', fixed: 'right' },
          ],
          data: [{ id: 'raw-1', name: 'A' }],
          rowKey: (row) => String(row.id),
          checkedRowKeys: ['raw-1'],
          scrollX: 1200,
          bordered: true,
          striped: true,
          fill: true,
        },
      })
      const table = wrapper.findComponent(NDataTable)
      expect(table.props()).toMatchObject({
        singleLine: false,
        bordered: true,
        striped: true,
        scrollX: 1200,
        checkedRowKeys: ['raw-1'],
        flexHeight: true,
        size: 'medium',
      })
      expect(wrapper.classes()).toContain(`app-table--${appearance}`)
      const rowClass = table.props('rowClassName')
      expect(typeof rowClass).toBe('function')
      if (typeof rowClass === 'function')
        expect(rowClass({ id: 'raw-1' }, 0)).toBe('app-table__row--selected')
      table.vm.$emit('update:checkedRowKeys', ['raw-2'])
      table.vm.$emit('update:sorter', { columnKey: 'name', order: 'ascend' })
      expect(wrapper.emitted('update:checkedRowKeys')).toEqual([[['raw-2']]])
      expect(wrapper.emitted('update:sorter')).toEqual([
        [{ columnKey: 'name', order: 'ascend' }],
      ])
      wrapper.unmount()
    },
  )
  it('does not enable an outer border, stripe or density by default', () => {
    const wrapper = shallowMount(AppTable, { props: { columns: [], data: [] } })
    expect(wrapper.findComponent(NDataTable).props()).toMatchObject({
      singleLine: false,
      bordered: false,
      striped: false,
      size: 'medium',
      themeOverrides: undefined,
    })
    wrapper.unmount()
  })
})
