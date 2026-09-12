import { shallowMount } from '@vue/test-utils'
import type { VNode } from 'vue'
import { describe, expect, it } from 'vitest'

import type { AutomationParameterPresetDto } from '@/entities/automation-application'
import AppButton from '@/shared/ui/AppButton.vue'

import ParameterPresetListTable from './ParameterPresetListTable.vue'

const preset: AutomationParameterPresetDto = {
  preset_id: 'preset-1',
  team_id: 'team-1',
  created_by_user_id: 'user-1',
  app_id: 'app-1',
  name: '日常采集',
  input_schema: { fields: [] },
  common_parameters: { 页码: 1 },
  shop_overrides: {},
  invalid_parameter_names: [],
  version: 1,
  created_at: '2026-09-12T00:00:00Z',
  updated_at: '2026-09-12T00:00:00Z',
}

describe('ParameterPresetListTable', () => {
  it('centers the fixed action column and keeps all three row actions', () => {
    const wrapper = shallowMount(ParameterPresetListTable, {
      props: {
        rows: [preset],
        appNameById: new Map([['app-1', '采集应用']]),
        loading: false,
        error: null,
      },
    })
    const columns = wrapper
      .findComponent({ name: 'DataTable' })
      .props('columns') as Array<{
      key?: string
      align?: string
      fixed?: string
      render?: (item: AutomationParameterPresetDto) => VNode
    }>
    const actions = columns.find((column) => column.key === 'actions')

    expect(actions).toMatchObject({ align: 'center', fixed: 'right' })
    const rendered = actions?.render?.(preset)
    const buttons = (rendered?.children as VNode[]).filter(
      (child) => child.type === AppButton,
    )
    expect(buttons).toHaveLength(3)

    ;(buttons[0]?.props?.onClick as () => void)()
    ;(buttons[1]?.props?.onClick as () => void)()
    ;(buttons[2]?.props?.onClick as () => void)()
    expect(wrapper.emitted('edit')).toEqual([[preset]])
    expect(wrapper.emitted('copy')).toEqual([[preset]])
    expect(wrapper.emitted('remove')).toEqual([[preset]])
  })
})
