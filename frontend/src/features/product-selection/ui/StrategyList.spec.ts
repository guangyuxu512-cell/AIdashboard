import { flushPromises, mount } from '@vue/test-utils'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createSelectionMockHandlers } from '../api/selection-mock-handlers'
import type {
  SelectionExecutionSummary,
  SelectionService,
} from '../model/contracts'
import StrategyList from './StrategyList.vue'

const messages = vi.hoisted(() => ({
  success: vi.fn(),
  warning: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
}))
vi.mock('naive-ui', async (original) => ({
  ...(await original<typeof import('naive-ui')>()),
  useMessage: () => messages,
}))
const DrawerStub = {
  name: 'StrategyDrawer',
  props: [
    'show',
    'strategy',
    'service',
    'contextKey',
    'executionDisabledReason',
  ],
  emits: ['retrieved', 'saved', 'update:show'],
  template: '<div />',
}
function execution(
  status: SelectionExecutionSummary['status'] = 'succeeded',
): SelectionExecutionSummary {
  return {
    run_id: 'explicit-run',
    request_shop_id: 'authorized-shop',
    status,
    result_count: 10,
    saved_count: 10,
    supplement_failed_count: 0,
    error_code: null,
  }
}
function render(
  run = vi.fn().mockResolvedValue(execution()),
  overrides: Partial<SelectionService> = {},
) {
  const service: SelectionService = {
    ...createSelectionMockHandlers(),
    available: false,
    manual: {
      capabilities: vi
        .fn()
        .mockResolvedValue({ manual_execution_available: true }),
      submit: vi.fn(),
    },
    latestRun: vi
      .fn()
      .mockResolvedValue({ ...execution(), run_id: 'historical-run' }),
    run,
    ...overrides,
  }
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  const wrapper = mount(StrategyList, {
    props: { service, contextKey: 'actor:team' },
    global: {
      plugins: [[VueQueryPlugin, { queryClient }]],
      stubs: {
        StrategyDrawer: DrawerStub,
        DataTable: {
          name: 'DataTable',
          props: ['emptyDescription', 'data', 'columns', 'scrollX'],
          template:
            '<div>{{ emptyDescription }}<span v-for="row in data" :key="row.id">{{ row.name }}</span></div>',
        },
        PaginationBar: {
          name: 'PaginationBar',
          props: ['page', 'pageSize', 'itemCount'],
          emits: ['update:page', 'update:pageSize'],
          template: '<div />',
        },
      },
    },
  })
  return { wrapper, queryClient, service }
}
describe('explicit selection completion messages', () => {
  beforeEach(() => vi.clearAllMocks())
  it('retains all existing columns, shares text width and does not force 1510px horizontal scrolling', async () => {
    const { wrapper, queryClient } = render()
    await flushPromises()
    const table = wrapper.findComponent({ name: 'DataTable' })
    const columns = table.props('columns')
    expect(columns.map((column: { key: string }) => column.key)).toEqual([
      'name',
      'shopName',
      'creatorName',
      'channel',
      'conditions',
      'execution',
      'latestResult',
      'enabled',
      'actions',
    ])
    expect(table.props('scrollX')).toBeUndefined()
    expect(
      columns.reduce(
        (sum: number, column: { width: number }) => sum + column.width,
        0,
      ),
    ).toBe(998)
    expect(
      columns.find((column: { key: string }) => column.key === 'actions').width,
    ).toBe(192)
    expect(
      columns.find((column: { key: string }) => column.key === 'enabled').width,
    ).toBe(68)
    for (const key of ['name', 'shopName', 'conditions', 'latestResult'])
      expect(
        columns.find((column: { key: string }) => column.key === key).ellipsis,
      ).toEqual({ tooltip: true })
    wrapper.unmount()
    queryClient.clear()
  })
  it('keeps page and filter after an existing edit but uses page one for a new save', async () => {
    const row = {
      ...(await createSelectionMockHandlers().strategies())[0]!,
      version: 1,
    }
    const read = vi
      .fn()
      .mockResolvedValue({ items: [row], total: 45, page: 2, pageSize: 20 })
    const { wrapper, queryClient } = render(undefined, {
      strategySaveAvailable: true,
      strategiesPage: read,
    })
    await flushPromises()
    await wrapper.find('input').setValue(row.name)
    await wrapper.find('input').trigger('keydown', { key: 'Enter' })
    await flushPromises()
    wrapper.findComponent({ name: 'PaginationBar' }).vm.$emit('update:page', 2)
    await flushPromises()
    const table = wrapper.findComponent({ name: 'DataTable' })
    const actions = table
      .props('columns')
      .find((column: { key: string }) => column.key === 'actions')
      .render(row)
    actions.children[1].props.onClick()
    await flushPromises()
    wrapper
      .findComponent(DrawerStub)
      .vm.$emit('saved', { ...row, version: 2, name: '已编辑' })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'PaginationBar' }).props('page')).toBe(
      2,
    )
    expect(read.mock.lastCall?.[0]).toMatchObject({
      page: 2,
      pageSize: 20,
      search: row.name,
    })
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '新建策略')!
      .trigger('click')
    wrapper
      .findComponent(DrawerStub)
      .vm.$emit('saved', { ...row, id: 'new-strategy' })
    await flushPromises()
    expect(wrapper.findComponent({ name: 'PaginationBar' }).props('page')).toBe(
      1,
    )
    wrapper.unmount()
    queryClient.clear()
  })
  it('applies the authoritative toggle response in place while the list refresh is pending', async () => {
    const rows = (await createSelectionMockHandlers().strategies())
      .slice(0, 2)
      .map((row) => ({ ...row, version: 1, enabled: false }))
    const changed = {
      ...rows[1]!,
      version: 2,
      enabled: true,
      latestResult: '已保存的最近结果',
    }
    let release!: (value: {
      items: typeof rows
      total: number
      page: number
      pageSize: number
    }) => void
    const pending = new Promise<{
      items: typeof rows
      total: number
      page: number
      pageSize: number
    }>((resolve) => {
      release = resolve
    })
    const read = vi
      .fn()
      .mockResolvedValueOnce({ items: rows, total: 2, page: 1, pageSize: 20 })
      .mockReturnValue(pending)
    const toggleStrategy = vi.fn().mockResolvedValue(changed)
    const { wrapper, queryClient } = render(undefined, {
      strategySaveAvailable: true,
      strategiesPage: read,
      toggleStrategy,
    })
    await flushPromises()
    const table = wrapper.findComponent({ name: 'DataTable' })
    const control = table
      .props('columns')
      .find((column: { key: string }) => column.key === 'enabled')
      .render(rows[1])
    const operation = control.props['onUpdate:modelValue'](true)
    await flushPromises()
    expect(table.props('data').map((row: { id: string }) => row.id)).toEqual(
      rows.map((row) => row.id),
    )
    expect(table.props('data')[1]).toMatchObject({
      enabled: true,
      version: 2,
      latestResult: '已保存的最近结果',
    })
    release({ items: [rows[0]!, changed], total: 2, page: 1, pageSize: 20 })
    await operation
    wrapper.unmount()
    queryClient.clear()
  })
  it('a read-only management capability retains saved rows while disabling new writes', async () => {
    const row = (await createSelectionMockHandlers().strategies())[0]!
    const read = vi
      .fn()
      .mockResolvedValue({ items: [row], total: 1, page: 1, pageSize: 20 })
    const { wrapper, queryClient } = render(undefined, {
      strategySaveAvailable: true,
      strategiesPage: read,
      manual: {
        capabilities: vi.fn().mockResolvedValue({
          strategy_save_available: false,
          manual_execution_available: false,
        }),
        submit: vi.fn(),
      },
    })
    await flushPromises()
    expect(read).toHaveBeenCalledOnce()
    expect(wrapper.text()).toContain(row.name)
    expect(
      wrapper
        .findAll('button')
        .find((button) => button.text() === '新建策略')!
        .attributes('disabled'),
    ).toBeDefined()
    wrapper.unmount()
    queryClient.clear()
  })
  it('never displays a historical completion banner or replays a toast on refresh/reentry', async () => {
    const { wrapper, queryClient, service } = render()
    await flushPromises()
    expect(wrapper.text()).toContain('策略保存与定时执行待接入')
    expect(wrapper.text()).not.toContain('已保存 10 项')
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '刷新')!
      .trigger('click')
    await flushPromises()
    expect(service.latestRun).toHaveBeenCalledTimes(2)
    expect(service.run).not.toHaveBeenCalled()
    expect(messages.success).not.toHaveBeenCalled()
    expect(messages.warning).not.toHaveBeenCalled()
    expect(messages.error).not.toHaveBeenCalled()
    wrapper.unmount()
    queryClient.clear()
    const reentry = render()
    await flushPromises()
    expect(messages.success).not.toHaveBeenCalled()
    reentry.wrapper.unmount()
    reentry.queryClient.clear()
  })
  it('forwards the explicit receipt to its workspace without owning completion tracking', async () => {
    const { wrapper, queryClient, service } = render()
    await flushPromises()
    wrapper
      .findComponent(DrawerStub)
      .vm.$emit('retrieved', execution('pending'))
    await flushPromises()
    expect(wrapper.emitted('submitted')).toEqual([[execution('pending')]])
    expect(service.run).not.toHaveBeenCalled()
    expect(messages.success).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('新建策略')
    expect(wrapper.text()).not.toContain('已保存 10 项')
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '刷新')!
      .trigger('click')
    await flushPromises()
    expect(wrapper.emitted('refresh-run-feedback')).toHaveLength(1)
    wrapper.unmount()
    queryClient.clear()
  })
})
