import { shallowMount } from '@vue/test-utils'
import type { VNode } from 'vue'
import { describe, expect, it } from 'vitest'

import type { TaskListItemViewModel } from '@/entities/task'
import AppButton from '@/shared/ui/AppButton.vue'

import TaskListTable from './TaskListTable.vue'

function findButton(node: unknown): VNode | null {
  if (!node || typeof node !== 'object') return null
  const vnode = node as VNode
  if (vnode.type === AppButton) return vnode
  if (Array.isArray(vnode.children)) {
    for (const child of vnode.children) {
      const found = findButton(child)
      if (found) return found
    }
  }
  return findButton(
    (vnode.children as { default?: () => unknown })?.default?.(),
  )
}

const row: TaskListItemViewModel = {
  taskId: 'task-stable',
  deviceId: 'device-1',
  deviceName: 'PC-11',
  skillId: 'system.sleep',
  executionName: '名称很长但必须保持在单行内的执行对象',
  status: 'running',
  progressDisplay: '3 / 10',
  currentMessage: '正在处理一条很长但不得撑高表格行的运行信息',
  startedAtDisplay: '2026-08-24 05:22:10',
  createdAt: '2026-08-24T05:22:08+08:00',
}

describe('TaskListTable', () => {
  it('uses task id as stable row key and keeps long cells ellipsized', () => {
    const wrapper = shallowMount(TaskListTable, { props: { rows: [row] } })
    const table = wrapper.findComponent({ name: 'DataTable' })
    const rowKey = table.props('rowKey') as (
      item: TaskListItemViewModel,
    ) => string
    const columns = table.props('columns') as Array<{
      key?: string
      ellipsis?: unknown
    }>

    expect(rowKey(row)).toBe('task-stable')
    expect(
      columns.find((column) => column.key === 'executionName')?.ellipsis,
    ).toBeTruthy()
    expect(
      columns.find((column) => column.key === 'currentMessage')?.ellipsis,
    ).toBeTruthy()
  })

  it('has one detail action which emits the selected task', () => {
    const wrapper = shallowMount(TaskListTable, { props: { rows: [row] } })
    const columns = wrapper
      .findComponent({ name: 'DataTable' })
      .props('columns') as Array<{
      key?: string
      render?: (item: TaskListItemViewModel) => VNode
    }>
    const rendered = columns
      .find((column) => column.key === 'actions')
      ?.render?.(row)
    const button = findButton(rendered)

    expect(button?.type).toBe(AppButton)
    ;(button?.props?.onClick as () => void)()
    expect(wrapper.emitted('detail')).toEqual([[row]])
  })
})
