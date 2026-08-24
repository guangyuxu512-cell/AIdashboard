import { shallowMount } from '@vue/test-utils'
import type { VNode } from 'vue'
import { describe, expect, it } from 'vitest'

import type { ScheduleListItemViewModel } from '@/entities/schedule'
import AppButton from '@/shared/ui/AppButton.vue'

import ScheduleListTable from './ScheduleListTable.vue'

const row: ScheduleListItemViewModel = {
  scheduleId: 'schedule-1',
  name: '每日商品发布',
  enabled: true,
  deviceId: 'device-1',
  deviceName: 'PC-11',
  executionType: 'yingdao_application',
  executionTypeDisplay: '影刀应用',
  skillId: 'yingdao.app.run',
  executionName: '原子模式单店模式',
  scheduleType: 'daily',
  localTime: '09:30',
  timezone: 'Asia/Shanghai',
  triggerRuleDisplay: '每天 09:30',
  nextRunAt: '2026-08-25T01:30:00Z',
  nextRunAtDisplay: '2026-08-25 09:30',
  latestRun: null,
  createdAt: '2026-08-24T00:00:00Z',
  createdAtDisplay: '2026-08-24 08:00',
  updatedAt: '2026-08-24T00:00:00Z',
  updatedAtDisplay: '2026-08-24 08:00',
}

describe('ScheduleListTable', () => {
  it('uses stable schedule id row key and the management fill viewport', () => {
    const wrapper = shallowMount(ScheduleListTable, { props: { rows: [row] } })
    const table = wrapper.findComponent({ name: 'DataTable' })
    const rowKey = table.props('rowKey') as (
      item: ScheduleListItemViewModel,
    ) => string

    expect(rowKey(row)).toBe('schedule-1')
    expect(table.props('viewport')).toBe('fill')
  })

  it('delegates initial loading, empty and error rendering to the shared DataTable', () => {
    const wrapper = shallowMount(ScheduleListTable, {
      props: { rows: [], loading: true, error: '请求失败' },
    })
    const table = wrapper.findComponent({ name: 'DataTable' })

    expect(table.props('data')).toEqual([])
    expect(table.props('loading')).toBe(true)
    expect(table.props('error')).toBe('请求失败')
    expect(table.props('emptyDescription')).toBe('暂无定时计划')
  })

  it('keeps view as the only row action', () => {
    const wrapper = shallowMount(ScheduleListTable, { props: { rows: [row] } })
    const columns = wrapper
      .findComponent({ name: 'DataTable' })
      .props('columns') as Array<{
      key?: string
      render?: (item: ScheduleListItemViewModel) => VNode
    }>
    const rendered = columns
      .find((column) => column.key === 'actions')
      ?.render?.(row)
    const buttons = (rendered?.children as VNode[]).filter(
      (child) => child.type === AppButton,
    )

    expect(buttons).toHaveLength(1)
    ;(buttons[0]?.props?.onClick as () => void)()
    expect(wrapper.emitted('detail')).toEqual([[row]])
  })
})
