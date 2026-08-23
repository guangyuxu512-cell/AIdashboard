import { shallowMount } from '@vue/test-utils'
import type { VNode } from 'vue'
import { describe, expect, it } from 'vitest'

import AppButton from '@/shared/ui/AppButton.vue'

import type { DeviceManagementRowViewModel } from '../model/types'
import DeviceListTable from './DeviceListTable.vue'

function findRuntimeButton(node: unknown): VNode | null {
  if (!node || typeof node !== 'object') return null
  const vnode = node as VNode
  if (
    vnode.type === AppButton &&
    typeof (vnode.children as { default?: () => string })?.default ===
      'function' &&
    (vnode.children as { default: () => string }).default() === '详情'
  ) {
    return vnode
  }
  if (Array.isArray(vnode.children)) {
    for (const child of vnode.children) {
      const found = findRuntimeButton(child)
      if (found) return found
    }
  }
  return null
}

function findButton(node: unknown, label: string): VNode | null {
  if (!node || typeof node !== 'object') return null
  const vnode = node as VNode
  if (
    vnode.type === AppButton &&
    typeof (vnode.children as { default?: () => string })?.default ===
      'function' &&
    (vnode.children as { default: () => string }).default() === label
  ) {
    return vnode
  }
  if (Array.isArray(vnode.children)) {
    for (const child of vnode.children) {
      const found = findButton(child, label)
      if (found) return found
    }
  }
  return null
}

describe('DeviceListTable runtime action', () => {
  it('keeps the current execution action compact and emits the task id', () => {
    const row = {
      deviceId: 'device-1',
      currentExecution: {
        label: '执行中',
        tone: 'info',
        name: '安全测试应用',
        latestMessage: '正在执行',
        taskId: 'task-1',
      },
    } as DeviceManagementRowViewModel
    const wrapper = shallowMount(DeviceListTable, { props: { rows: [row] } })
    const columns = wrapper
      .findComponent({ name: 'DataTable' })
      .props('columns') as Array<{
      key?: string
      render?: (value: DeviceManagementRowViewModel) => VNode
    }>
    const rendered = columns
      .find((column) => column.key === 'currentExecution')
      ?.render?.(row)
    const button = findRuntimeButton(rendered)

    expect(button).not.toBeNull()
    ;(button?.props?.onClick as () => void)()
    expect(wrapper.emitted('view-runtime')).toEqual([['task-1']])
  })

  it('uses deviceId as the stable row key and omits the current step', () => {
    const row = {
      deviceId: 'device-stable',
      currentExecution: {
        label: '执行中',
        tone: 'info',
        name: '名称很长但必须保持单行的影刀应用',
        latestMessage: '上传图片 3/10',
        taskId: 'task-1',
      },
    } as DeviceManagementRowViewModel
    const wrapper = shallowMount(DeviceListTable, { props: { rows: [row] } })
    const table = wrapper.findComponent({ name: 'DataTable' })
    const rowKey = table.props('rowKey') as (
      value: DeviceManagementRowViewModel,
    ) => string
    const columns = table.props('columns') as Array<{
      key?: string
      render?: (value: DeviceManagementRowViewModel) => VNode
    }>
    const rendered = columns
      .find((column) => column.key === 'currentExecution')
      ?.render?.(row)

    expect(rowKey(row)).toBe('device-stable')
    expect(JSON.stringify(rendered)).not.toContain('上传图片 3/10')
  })

  it('replaces the list edit action with the capability entry', () => {
    const row = {
      deviceId: 'device-1',
      deviceName: 'PC-11',
      enabled: true,
    } as DeviceManagementRowViewModel
    const wrapper = shallowMount(DeviceListTable, { props: { rows: [row] } })
    const columns = wrapper
      .findComponent({ name: 'DataTable' })
      .props('columns') as Array<{
      key?: string
      render?: (value: DeviceManagementRowViewModel) => VNode
    }>
    const rendered = columns.find((column) => column.key === 'actions')?.render?.(row)
    const capabilityButton = findButton(rendered, '能力')

    expect(capabilityButton).not.toBeNull()
    expect(findButton(rendered, '编辑')).toBeNull()
    ;(capabilityButton?.props?.onClick as () => void)()
    expect(wrapper.emitted('capability')).toEqual([[row]])
  })
})
