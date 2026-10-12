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
          props: ['emptyDescription', 'data'],
          template:
            '<div>{{ emptyDescription }}<span v-for="row in data" :key="row.id">{{ row.name }}</span></div>',
        },
        PaginationBar: true,
      },
    },
  })
  return { wrapper, queryClient, service }
}
describe('explicit selection completion messages', () => {
  beforeEach(() => vi.clearAllMocks())
  it('a read-only management capability retains saved rows while disabling new writes', async () => {
    const row = (await createSelectionMockHandlers().strategies())[0]!
    const read = vi
      .fn()
      .mockResolvedValue({ items: [row], total: 1, page: 1, pageSize: 20 })
    const { wrapper, queryClient } = render(undefined, {
      strategySaveAvailable: true,
      strategiesPage: read,
      manual: {
        capabilities: vi
          .fn()
          .mockResolvedValue({
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
