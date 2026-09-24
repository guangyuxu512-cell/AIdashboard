import { mount } from '@vue/test-utils'
import { NConfigProvider } from 'naive-ui'
import { describe, expect, it } from 'vitest'

import OperatingDashboardTable from './OperatingDashboardTable.vue'

function mountTable(
  props: InstanceType<typeof OperatingDashboardTable>['$props'],
) {
  return mount(
    {
      components: { NConfigProvider, OperatingDashboardTable },
      props: ['rows', 'emptyDescription', 'sort', 'sortingEnabled'],
      template: `
      <NConfigProvider>
        <OperatingDashboardTable
          :rows="rows"
          :empty-description="emptyDescription"
          :sort="sort"
          :sorting-enabled="sortingEnabled"
        />
      </NConfigProvider>
    `,
    },
    { props },
  )
}

describe('OperatingDashboardTable', () => {
  it('keeps its headers visible when operating data is unavailable', () => {
    const wrapper = mountTable({
      rows: [],
      emptyDescription: '经营数据暂不可用',
    })

    expect(wrapper.text()).toContain('经营数据暂不可用')
    expect(wrapper.text()).toContain('店铺')
    expect(wrapper.text()).toContain('商家体验分')
  })

  it('shows unavailable metrics as dashes without inventing a collection time', () => {
    const wrapper = mountTable({
      rows: [
        {
          shopId: 'shop-pdd',
          shopName: '拼多多店铺',
          platform: 'pdd',
          turnoverCents: null,
          orderCount: null,
          refundOrderCount: null,
          experience: null,
          collectedAt: null,
        },
      ],
    })

    expect(wrapper.text()).toContain('拼多多店铺')
    expect(wrapper.text()).toContain('—')
  })

  it('uses native sortable headers for both Mock and server-paginated results', () => {
    const rows = [
      {
        shopId: 'shop-a',
        shopName: '店铺 A',
        platform: 'douyin' as const,
        turnoverCents: 1,
        orderCount: 1,
        refundOrderCount: 0,
        experience: null,
        collectedAt: '2026-09-20T08:00:00+08:00',
      },
    ]
    const mockTable = mountTable({
      rows,
      sortingEnabled: true,
      sort: { field: 'turnoverCents', direction: 'desc' },
    })
    const realTable = mountTable({
      rows,
      sortingEnabled: true,
      sort: { field: 'turnoverCents', direction: 'desc' },
    })

    expect(mockTable.findAll('.n-data-table-th--sortable')).toHaveLength(5)
    expect(mockTable.text()).toContain('退款订单数')
    expect(
      mockTable
        .get('[data-col-key="turnoverCents"]')
        .find('.n-data-table-sorter')
        .classes(),
    ).toContain('n-data-table-sorter--desc')
    expect(realTable.findAll('.n-data-table-th--sortable')).toHaveLength(5)
  })
})
