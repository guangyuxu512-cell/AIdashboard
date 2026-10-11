import { flushPromises, mount } from '@vue/test-utils'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { createPinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '@/stores/auth'
import { createSelectionService } from '../api/selection-service'
import { createSelectionMockHandlers } from '../api/selection-mock-handlers'
import type {
  SelectionExecutionSummary,
  SelectionService,
} from '../model/contracts'
import SelectionWorkspace from './SelectionWorkspace.vue'
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
vi.mock('../api/selection-service', () => ({
  createSelectionService: vi.fn(),
  SELECTION_UNAVAILABLE: '选品能力尚未接入',
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
const PoolStub = {
  name: 'CandidatePool',
  props: ['service', 'contextKey'],
  emits: ['refresh-run-feedback'],
  template:
    '<button @click="$emit(\'refresh-run-feedback\')">刷新列表</button>',
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
    error_stage: status === 'failed' ? 'platform_business' : null,
  }
}
function render(
  run = vi.fn().mockResolvedValue(execution()),
  manualExecutionAvailable = true,
) {
  const service: SelectionService = {
    ...createSelectionMockHandlers(),
    available: false,
    candidatesAvailable: true,
    manual: {
      capabilities: vi.fn().mockResolvedValue({
        manual_execution_available: manualExecutionAvailable,
      }),
      submit: vi.fn(),
    },
    latestRun: vi
      .fn()
      .mockResolvedValue({ ...execution(), run_id: 'historical-run' }),
    run,
  }
  vi.mocked(createSelectionService).mockResolvedValue(service)
  const pinia = createPinia()
  const auth = useAuthStore(pinia)
  auth.currentUser = { userId: 'actor', displayName: '测试人员' }
  auth.activeTeamId = 'team'
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  const wrapper = mount(SelectionWorkspace, {
    props: { panel: 'selection-strategy' },
    global: {
      plugins: [pinia, [VueQueryPlugin, { queryClient }]],
      stubs: {
        StrategyDrawer: DrawerStub,
        CandidatePool: PoolStub,
        DataTable: {
          name: 'DataTable',
          props: ['columns', 'data', 'emptyDescription'],
          template: '<div>{{ emptyDescription }}</div>',
        },
        PaginationBar: true,
      },
    },
  })
  return { wrapper, queryClient, service, auth }
}
function pendingResult() {
  let resolve!: (value: SelectionExecutionSummary) => void
  const run = vi.fn().mockImplementation(
    () =>
      new Promise((done) => {
        resolve = done
      }),
  )
  return { run, resolve: (value: SelectionExecutionSummary) => resolve(value) }
}
describe('submitted selection feedback survives panel changes', () => {
  beforeEach(() => vi.clearAllMocks())
  it.each([true, false])(
    'keeps the approved Real strategy management when manual execution availability is %s',
    async (available) => {
      const { wrapper, queryClient, service } = render(undefined, available)
      const strategies = vi.spyOn(service, 'strategies')
      const saveStrategy = vi.spyOn(service, 'saveStrategy')
      await flushPromises()
      expect(wrapper.findComponent(StrategyList).exists()).toBe(true)
      expect(wrapper.text()).toContain('刷新')
      expect(wrapper.text()).toContain('达人登录')
      expect(wrapper.text()).toContain('新建策略')
      expect(wrapper.text()).toContain('策略保存与定时执行待接入')
      const table = wrapper.findComponent({ name: 'DataTable' })
      expect(
        table.props('columns').map((column: { title: string }) => column.title),
      ).toEqual([
        '策略名',
        '请求店铺',
        '达人账号',
        '渠道',
        '条件摘要',
        '执行方式',
        '最近结果',
        '状态',
        '操作',
      ])
      expect(table.props('data')).toEqual([])
      await wrapper
        .findAll('button')
        .find((button) => button.text() === '新建策略')!
        .trigger('click')
      const drawer = wrapper.findComponent(DrawerStub)
      expect(drawer.props('show')).toBe(true)
      expect(drawer.props('executionDisabledReason')).toBe(
        available ? null : '此环境手动获取未启用，已入库结果仍可查询',
      )
      // Preserve the original UI without loading demo strategies or implicitly
      // submitting/saving because a manual capability is unavailable.
      expect(strategies).not.toHaveBeenCalled()
      expect(saveStrategy).not.toHaveBeenCalled()
      expect(service.manual!.submit).not.toHaveBeenCalled()
      wrapper.unmount()
      queryClient.clear()
    },
  )
  it.each([
    ['succeeded', 'success'],
    ['partial', 'warning'],
    ['failed', 'error'],
    ['interrupted', 'error'],
  ] as const)(
    'notifies %s once after submitting pending and unmounting StrategyList',
    async (status, kind) => {
      const pending = pendingResult()
      const { wrapper, queryClient, service } = render(pending.run)
      await flushPromises()
      wrapper
        .findComponent(DrawerStub)
        .vm.$emit('retrieved', execution('pending'))
      await flushPromises()
      expect(service.run).toHaveBeenCalledExactlyOnceWith('explicit-run')
      await wrapper.setProps({ panel: 'candidate-pool' })
      expect(wrapper.findComponent(StrategyList).exists()).toBe(false)
      pending.resolve(execution(status))
      await flushPromises()
      expect(messages[kind]).toHaveBeenCalledOnce()
      await wrapper.get('button').trigger('click')
      await wrapper.setProps({ panel: 'selection-strategy' })
      await flushPromises()
      expect(wrapper.findComponent(StrategyList).exists()).toBe(true)
      expect(wrapper.text()).toContain('新建策略')
      expect(messages[kind]).toHaveBeenCalledOnce()
      expect(service.run).toHaveBeenCalledOnce()
      wrapper.unmount()
      queryClient.clear()
    },
  )
  it('never registers latest history on refresh or workspace reentry', async () => {
    const { wrapper, queryClient, service } = render()
    await flushPromises()
    await wrapper.setProps({ panel: 'candidate-pool' })
    await wrapper.get('button').trigger('click')
    await wrapper.setProps({ panel: 'selection-strategy' })
    await flushPromises()
    expect(service.run).not.toHaveBeenCalled()
    expect(messages.success).not.toHaveBeenCalled()
    wrapper.unmount()
    queryClient.clear()
    const reentry = render()
    await flushPromises()
    expect(reentry.service.run).not.toHaveBeenCalled()
    expect(messages.success).not.toHaveBeenCalled()
    reentry.wrapper.unmount()
    reentry.queryClient.clear()
  })
  it.each(['actor', 'team'] as const)(
    'discards a late run when %s changes',
    async (context) => {
      const pending = pendingResult()
      const { wrapper, queryClient, auth } = render(pending.run)
      await flushPromises()
      wrapper
        .findComponent(DrawerStub)
        .vm.$emit('retrieved', execution('pending'))
      await flushPromises()
      await wrapper.setProps({ panel: 'candidate-pool' })
      if (context === 'actor')
        auth.currentUser = { userId: 'other-actor', displayName: '另一人员' }
      else auth.activeTeamId = 'other-team'
      await flushPromises()
      pending.resolve(execution())
      await flushPromises()
      expect(messages.success).not.toHaveBeenCalled()
      expect(messages.warning).not.toHaveBeenCalled()
      expect(messages.error).not.toHaveBeenCalled()
      wrapper.unmount()
      queryClient.clear()
    },
  )
  it('does not replay a run that completed after leaving the workspace', async () => {
    const pending = pendingResult()
    const { wrapper, queryClient } = render(pending.run)
    await flushPromises()
    wrapper
      .findComponent(DrawerStub)
      .vm.$emit('retrieved', execution('pending'))
    await flushPromises()
    wrapper.unmount()
    pending.resolve(execution())
    await flushPromises()
    expect(messages.success).not.toHaveBeenCalled()
    queryClient.clear()
    const reentry = render()
    await flushPromises()
    expect(messages.success).not.toHaveBeenCalled()
    reentry.wrapper.unmount()
    reentry.queryClient.clear()
  })
})
