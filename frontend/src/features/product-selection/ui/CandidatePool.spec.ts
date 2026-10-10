import { flushPromises, mount } from '@vue/test-utils'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { defineComponent, h } from 'vue'
import { NMessageProvider } from 'naive-ui'
import { describe, expect, it, vi } from 'vitest'
import { AppButton } from '@/shared/ui'
import { createSelectionMockHandlers } from '../api/selection-mock-handlers'
import type { BatchCollectReceipt, SelectionService } from '../model/contracts'
import CandidatePool from './CandidatePool.vue'

const TableStub = defineComponent({
  name: 'DataTable',
  props: ['data', 'checkedRowKeys', 'columns', 'themeOverrides', 'scrollX'],
  emits: ['update:checkedRowKeys'],
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
  const button = () =>
    wrapper
      .findAllComponents(AppButton)
      .find((item) => item.text() === '批量采集资料')!
  const dispose = () => {
    wrapper.unmount()
    queryClient.clear()
  }
  return { wrapper, table, button, dispose }
}

describe('candidate selection and batch demo', () => {
  it.each([
    ['succeeded', 0, null, '最近获取成功，返回 0 项'],
    [
      'failed',
      null,
      'PLATFORM_RESPONSE_INVALID',
      '最近获取失败：PLATFORM_RESPONSE_INVALID',
    ],
    [
      'partial',
      10,
      'PRODUCT_SELECTION_BASIC_INFO_INCOMPLETE',
      '最近获取部分完成',
    ],
    ['interrupted', null, null, '最近获取已中断'],
  ] as const)(
    'reads Real %s state independently from empty candidates and disables unsupported writes',
    async (status, count, error, message) => {
      const service = createSelectionMockHandlers()
      const candidates = vi
        .spyOn(service, 'candidates')
        .mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 10 })
      const latestRun = vi
        .fn()
        .mockResolvedValue({
          run_id: 'canonical',
          request_shop_id: 'shop',
          status,
          result_count: count,
          saved_count: count ?? 0,
          supplement_failed_count: 0,
          error_code: error,
        })
      const { wrapper, table, button, dispose } = render({
        ...service,
        available: false,
        candidatesAvailable: true,
        latestRun,
      })
      await flushPromises()
      expect(wrapper.text()).toContain(message)
      expect(table.props('data')).toEqual([])
      expect(button().props('disabled')).toBe(true)
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
  it('centers the two-line title and all columns, keeps the agreed base widths and scope out of the list', async () => {
    const { wrapper, table, button, dispose } = render(
      createSelectionMockHandlers(),
    )
    await flushPromises()
    const columns = table.props('columns')
    expect(
      columns.map(
        (column: { key?: string; type?: string }) => column.key ?? column.type,
      ),
    ).toEqual([
      'selection',
      'image',
      'title',
      'merchant',
      'category',
      'rank',
      'discovery',
      'priceBand',
      'negativeReviewRate',
      'listedAt',
      'collectionStatus',
      'actions',
    ])
    for (const column of columns) {
      expect(column.align).toBe('center')
    }
    const widths = columns.map((column: { width: number }) => column.width)
    expect(widths).toEqual([
      44, 88, 280, 140, 100, 88, 88, 112, 96, 140, 100, 220,
    ])
    expect(
      widths.reduce((total: number, width: number) => total + width, 0),
    ).toBe(1496)
    expect(table.props('scrollX')).toBe(1496)
    const title = columns
      .find((column: { key: string }) => column.key === 'title')
      .render(table.props('data')[0])
    expect(title.props).toMatchObject({
      lineClamp: 2,
      tooltip: true,
      style: { width: '100%', textAlign: 'center' },
    })
    expect(columns.at(-1).fixed).toBe('right')
    expect(columns.at(-1).width).toBe(220)
    expect(table.props('themeOverrides')).toEqual({
      tdPaddingMedium: 'var(--space-2) var(--space-3)',
      thPaddingMedium: 'var(--space-2) var(--space-3)',
    })
    expect(button().props('tone')).toBe('primary')
    expect(wrapper.text()).not.toContain('短视频商品榜 · 近7天 · 第1–200名')
    expect(wrapper.text()).not.toContain('查看范围')
    expect(wrapper.text()).not.toContain('已选')
    expect(wrapper.text()).not.toContain('全选仅当前页')
    expect(wrapper.text()).not.toContain('2026-10-08 12:00')
    dispose()
  })
  it('guards empty/duplicate submissions, unchecks success and retains failed selections with per-item feedback', async () => {
    let finish!: (receipt: BatchCollectReceipt) => void
    const service = createSelectionMockHandlers()
    const batch = vi.spyOn(service, 'collectBatch').mockImplementation(
      () =>
        new Promise((resolve) => {
          finish = resolve
        }),
    )
    const { wrapper, table, button, dispose } = render(service)
    await flushPromises()
    expect(table.props('data')).toHaveLength(10)
    expect(button().props('disabled')).toBe(true)
    button().vm.$emit('click', new MouseEvent('click'))
    await flushPromises()
    expect(batch).not.toHaveBeenCalled()
    table.vm.$emit('update:checkedRowKeys', ['candidate-000', 'candidate-001'])
    await flushPromises()
    expect(wrapper.text()).toContain('已选 2 项')
    button().vm.$emit('click', new MouseEvent('click'))
    button().vm.$emit('click', new MouseEvent('click'))
    await flushPromises()
    expect(batch).toHaveBeenCalledExactlyOnceWith([
      'candidate-000',
      'candidate-001',
    ])
    expect(button().props('disabled')).toBe(true)
    finish({
      mode: 'mock',
      results: [
        {
          candidateId: 'candidate-000',
          candidateIds: ['candidate-000'],
          productId: '9087654321098765000',
          state: 'demo',
          message: '演示',
        },
        {
          candidateId: 'candidate-001',
          candidateIds: ['candidate-001'],
          productId: '9087654321098765001',
          state: 'failed',
          message: '演示采集失败，请重试',
        },
      ],
    })
    await flushPromises()
    expect(table.props('checkedRowKeys')).toEqual(['candidate-001'])
    expect(wrapper.text()).toContain(
      '9087654321098765001：演示采集失败，请重试',
    )
    expect(button().props('disabled')).toBe(false)
    batch.mockImplementationOnce((ids) =>
      Promise.resolve({
        mode: 'mock',
        results: ids.map((id) => ({
          candidateId: id,
          candidateIds: [id],
          productId: '9087654321098765001',
          state: 'demo',
          message: '演示',
        })),
      }),
    )
    button().vm.$emit('click', new MouseEvent('click'))
    await flushPromises()
    expect(table.props('checkedRowKeys')).toEqual([])
    expect(button().props('disabled')).toBe(true)
    dispose()
  })
  it('keeps all selections on a request failure and clears them on page/filter changes', async () => {
    const service = createSelectionMockHandlers()
    vi.spyOn(service, 'collectBatch').mockRejectedValue(
      new Error('演示请求失败'),
    )
    const { wrapper, table, button, dispose } = render(service)
    await flushPromises()
    table.vm.$emit('update:checkedRowKeys', ['candidate-000'])
    await flushPromises()
    button().vm.$emit('click', new MouseEvent('click'))
    await flushPromises()
    expect(table.props('checkedRowKeys')).toEqual(['candidate-000'])
    wrapper.findComponent({ name: 'PaginationBar' }).vm.$emit('update:page', 2)
    await flushPromises()
    expect(table.props('checkedRowKeys')).toEqual([])
    expect(table.props('data')[0].id).toBe('candidate-010')
    expect(wrapper.text()).not.toContain('已选')
    dispose()
  })
})
