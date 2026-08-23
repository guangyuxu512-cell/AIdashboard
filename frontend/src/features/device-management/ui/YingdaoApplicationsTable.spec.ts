import { shallowMount } from '@vue/test-utils'
import { NTooltip, type DataTableColumns } from 'naive-ui'
import { describe, expect, it, vi } from 'vitest'
import type { VNode } from 'vue'

import type { ProviderApplicationViewModel } from '@/entities/device'
import DataTable from '@/shared/components/DataTable.vue'

import YingdaoApplicationsTable from './YingdaoApplicationsTable.vue'

vi.mock('naive-ui', async (importOriginal) => {
  const actual = await importOriginal<typeof import('naive-ui')>()
  return {
    ...actual,
    useMessage: () => ({ success: vi.fn(), error: vi.fn() }),
  }
})

const application: ProviderApplicationViewModel = {
  appId: 'app-1',
  appName: '应用 1',
  versionId: '1',
}

describe('YingdaoApplicationsTable', () => {
  it('uses a neutral empty description for a successful empty list', () => {
    const wrapper = shallowMount(YingdaoApplicationsTable, {
      props: { applications: [] },
    })

    expect(wrapper.findComponent(DataTable).props('emptyDescription')).toBe(
      '暂无可访问的影刀应用',
    )
  })

  it('wraps a disabled run action in a tooltip with the exact reason', () => {
    const reason = '影刀 6.3.6 当前需要登录'
    const wrapper = shallowMount(YingdaoApplicationsTable, {
      props: { applications: [application], runDisabledReason: reason },
    })
    const columns = wrapper
      .findComponent(DataTable)
      .props('columns') as DataTableColumns<ProviderApplicationViewModel>
    const actionColumn = columns.find(
      (column) => 'key' in column && column.key === 'actions',
    ) as
      | {
          render?: (
            row: ProviderApplicationViewModel,
            rowIndex: number,
          ) => VNode
        }
      | undefined
    const rendered = actionColumn?.render?.(application, 0) as VNode
    const tooltip = (rendered.children as VNode[])[0]
    const slots = tooltip.children as { default: () => string }

    expect(tooltip.type).toBe(NTooltip)
    expect(slots.default()).toBe(reason)
  })
})
