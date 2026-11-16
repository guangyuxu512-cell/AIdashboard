import { flushPromises, mount } from '@vue/test-utils'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { defineComponent, h } from 'vue'
import { NMessageProvider } from 'naive-ui'
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'
import { AppButton } from '@/shared/ui'
import {
  FilterBar,
  ManagementListSection,
  PaginationBar,
} from '@/shared/components'
import { createSelectionMockHandlers } from '../api/selection-mock-handlers'
import type { SelectionService } from '../model/contracts'
import CandidatePool from './CandidatePool.vue'
import ShopSelector from '@/entities/shop/ui/ShopSelector.vue'
import { ProductInfoCell } from '@/entities/product'

const TableStub = defineComponent({
  name: 'DataTable',
  props: ['data', 'columns', 'themeOverrides', 'scrollX', 'emptyDescription'],
  template: '<div />',
})
function render(service: SelectionService) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  const wrapper = mount(
    defineComponent({
      setup: () => () =>
        h(
          NMessageProvider,
          {},
          {
            default: () =>
              h(CandidatePool, { service, contextKey: 'actor:team' }),
          },
        ),
    }),
    {
      global: {
        plugins: [[VueQueryPlugin, { queryClient }]],
        stubs: {
          DataTable: TableStub,
          ShopSelector: true,
          CandidateDetailDrawer: true,
        },
      },
    },
  )
  const table = wrapper.findComponent(TableStub)
  const dispose = () => {
    wrapper.unmount()
    queryClient.clear()
  }
  return { wrapper, table, dispose }
}

describe('candidate list', () => {
  beforeAll(() =>
    document.documentElement.style.setProperty(
      '--list-compact-control-height',
      '28px',
    ),
  )
  afterAll(() =>
    document.documentElement.style.removeProperty(
      '--list-compact-control-height',
    ),
  )
  it('clearing shop removes the filter, resets pagination and only reads results', async () => {
    const service = createSelectionMockHandlers()
    const candidates = vi.spyOn(service, 'candidates')
    const retrieve = vi.spyOn(service, 'retrieve')
    const { wrapper, dispose } = render(service)
    await flushPromises()
    expect(candidates.mock.calls[0]?.[0].pageSize).toBe(20)
    const selector = wrapper.findComponent(ShopSelector)
    expect(selector.props('clearable')).toBe(true)
    selector.vm.$emit('update:modelValue', 'shop-fixture-001')
    await flushPromises()
    selector.vm.$emit('update:modelValue', null)
    await flushPromises()
    expect(candidates.mock.calls.at(-1)?.[0]).toMatchObject({
      shopId: null,
      page: 1,
    })
    expect(retrieve).not.toHaveBeenCalled()
    dispose()
  })
  it.each([
    ['succeeded', 0, null, '所选范围暂无候选商品'],
    [
      'failed',
      null,
      'PLATFORM_RESPONSE_INVALID',
      '获取失败 · PLATFORM_RESPONSE_INVALID',
    ],
    [
      'partial',
      10,
      'PRODUCT_SELECTION_BASIC_INFO_INCOMPLETE',
      '所选范围暂无候选商品',
    ],
    ['interrupted', null, null, '执行中断'],
  ] as const)(
    'reads Real %s state independently from empty candidates and disables unsupported writes',
    async (status, count, error, message) => {
      const service = createSelectionMockHandlers()
      const candidates = vi
        .spyOn(service, 'candidates')
        .mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 10 })
      const latestRun = vi.fn().mockResolvedValue({
        run_id: 'canonical',
        request_shop_id: 'shop',
        status,
        result_count: count,
        saved_count: count ?? 0,
        supplement_failed_count: 0,
        error_code: error,
      })
      const { wrapper, table, dispose } = render({
        ...service,
        available: false,
        candidatesAvailable: true,
        latestRun,
      })
      await flushPromises()
      expect(table.props('emptyDescription')).toContain(message)
      expect(wrapper.text()).not.toContain('获取完成')
      expect(table.props('data')).toEqual([])
      expect(wrapper.text()).not.toContain('批量采集资料')
      expect(
        table
          .props('columns')
          .find((item: { key: string }) => item.key === 'negativeReviewRate')
          .sorter,
      ).toBe(false)
      const refresh = wrapper
        .findAllComponents(AppButton)
        .find((item) => item.text() === '刷新列表')!
      refresh.vm.$emit('click', new MouseEvent('click'))
      await flushPromises()
      expect(candidates).toHaveBeenCalledTimes(2)
      expect(latestRun).toHaveBeenCalledTimes(2)
      dispose()
    },
  )
  it('reuses one product identity column, preserves other columns and keeps scope out of the list', async () => {
    const { wrapper, table, dispose } = render(createSelectionMockHandlers())
    await flushPromises()
    const columns = table.props('columns')
    expect(
      columns.map(
        (column: { key?: string; type?: string }) => column.key ?? column.type,
      ),
    ).toEqual([
      'productInfo',
      'merchant',
      'category',
      'rank',
      'firstListed',
      'discovery',
      'priceBand',
      'negativeReviewRate',
      'listedAt',
      'actions',
    ])
    for (const column of columns) {
      expect(column.align).toBe('center')
    }
    const widths = columns.map((column: { width: number }) => column.width)
    expect(widths[0]).toBeGreaterThanOrEqual(340)
    expect(widths[0]).toBeLessThanOrEqual(360)
    expect(widths.at(-1)).toBe(220)
    expect(
      widths.reduce((total: number, width: number) => total + width, 0),
    ).toBe(1494)
    expect(table.props('scrollX')).toBeUndefined()
    const product = columns
      .find((column: { key: string }) => column.key === 'productInfo')
      .render(table.props('data')[0])
    const row = table.props('data')[0]
    expect(product.type).toBe(ProductInfoCell)
    expect(product.props).toMatchObject({
      title: row.title,
      productId: row.productId,
      imageUrl: row.imageUrl,
      density: 'compact',
    })
    const firstListed = columns.find(
      (column: { key: string }) => column.key === 'firstListed',
    )
    expect(firstListed.width).toBe(84)
    expect(firstListed.sorter).toBeUndefined()
    for (const [value, label, depth] of [
      [true, '是', 1],
      [false, '否', 1],
      [null, '—', 3],
    ] as const) {
      const cell = firstListed.render({ ...row, firstListed: value })
      expect(cell.props.depth).toBe(depth)
      expect(cell.children.default()).toBe(label)
    }
    expect(columns.at(-1).fixed).toBe('right')
    expect(columns.at(-1).width).toBe(220)
    expect(table.props('themeOverrides')).toBeUndefined()
    for (const component of [FilterBar, ManagementListSection, PaginationBar])
      expect(wrapper.findComponent(component).props('density')).toBe('compact')
    // Teleport alone does not reset provide. Detail must remain a sibling.
    expect(
      wrapper
        .findComponent(ManagementListSection)
        .find('candidate-detail-drawer-stub')
        .exists(),
    ).toBe(false)
    expect(wrapper.find('candidate-detail-drawer-stub').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('批量采集资料')
    expect(wrapper.text()).not.toContain('短视频商品榜 · 近7天 · 第1–200名')
    expect(wrapper.text()).not.toContain('查看范围')
    expect(wrapper.text()).not.toContain('已选')
    expect(wrapper.text()).not.toContain('全选仅当前页')
    expect(wrapper.text()).not.toContain('2026-10-08 12:00')
    dispose()
  })
})
