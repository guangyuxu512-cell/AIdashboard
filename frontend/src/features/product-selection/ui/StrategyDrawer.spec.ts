import { flushPromises, mount } from '@vue/test-utils'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { defineComponent, h } from 'vue'
import { NMessageProvider, NTooltip } from 'naive-ui'
import { describe, expect, it, vi } from 'vitest'
import { createSelectionMockHandlers } from '../api/selection-mock-handlers'
import type {
  CategoryNode,
  SelectionService,
  SelectionStrategy,
} from '../model/contracts'
import { AppCheckbox, AppInput, AppRadio } from '@/shared/ui'
import CategorySelector from './CategorySelector.vue'
import StrategyDrawer from './StrategyDrawer.vue'

const ShopStub = defineComponent({
  name: 'ShopSelector',
  props: ['modelValue'],
  emits: ['update:modelValue'],
  template: '<div />',
})
function render(
  service: SelectionService,
  strategy: SelectionStrategy | null = null,
  manualOnly = false,
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  const Wrapper = defineComponent({
    setup: () => () =>
      h(
        NMessageProvider,
        {},
        {
          default: () =>
            h(StrategyDrawer, {
              show: true,
              strategy,
              service,
              contextKey: 'actor:team',
              manualOnly,
            }),
        },
      ),
  })
  const wrapper = mount(Wrapper, {
    global: {
      plugins: [[VueQueryPlugin, { queryClient }]],
      stubs: {
        AppDrawer: { template: '<div><slot /><slot name="footer" /></div>' },
        ShopSelector: ShopStub,
      },
    },
  })
  return { wrapper, queryClient }
}

describe('strategy shop category loading', () => {
  it('Real manual uses a stable submission key after uncertain failure, never saves, and disables unsupported periods', async () => {
    const service = createSelectionMockHandlers()
    const submit = vi
      .fn()
      .mockRejectedValueOnce(new Error('提交响应暂未确认'))
      .mockResolvedValueOnce({ reused: true })
    service.manual = { capabilities: vi.fn(), submit }
    const save = vi.spyOn(service, 'saveStrategy'),
      demo = vi.spyOn(service, 'retrieve')
    const { wrapper, queryClient } = render(service, null, true)
    wrapper
      .findComponent(ShopStub)
      .vm.$emit('update:modelValue', (await service.strategies())[0]!.shopId)
    await flushPromises()
    wrapper
      .findComponent(CategorySelector)
      .vm.$emit('update:modelValue', 'actual-category')
    await flushPromises()
    const radio = wrapper.findAllComponents(AppRadio)[0]!
    expect(radio.props('modelValue')).toBe('7d')
    expect(
      radio
        .props('options')
        .filter((item) => !item.disabled),
    ).toEqual([{ value: '7d', label: '近7天', disabled: false }])
    expect(wrapper.text()).not.toContain('保存策略')
    const get = wrapper
      .findAll('button')
      .find((button) => button.text() === '立即获取')!
    await get.trigger('click')
    await flushPromises()
    await get.trigger('click')
    await flushPromises()
    expect(submit).toHaveBeenCalledTimes(2)
    expect(submit.mock.calls[0]![1]).toBe(submit.mock.calls[1]![1])
    expect(save).not.toHaveBeenCalled()
    expect(demo).not.toHaveBeenCalled()
    expect(
      wrapper.findComponent(StrategyDrawer).emitted('retrieved'),
    ).toHaveLength(1)
    wrapper.unmount()
    queryClient.clear()
  })
  it('retrieves an existing strategy by ID and signals a result refresh without saving its edited draft', async () => {
    const service = createSelectionMockHandlers()
    const initial = (await service.strategies())[0]!
    const retrieve = vi.spyOn(service, 'retrieve')
    const save = vi.spyOn(service, 'saveStrategy')
    const { wrapper, queryClient } = render(service, initial)
    await flushPromises()
    const name = wrapper.findComponent(AppInput)
    name.vm.$emit('update:modelValue', '未保存的修改')
    wrapper.findAllComponents(AppRadio)[0]!.vm.$emit('update:modelValue', '7d')
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '立即获取')!
      .trigger('click')
    await flushPromises()

    expect(retrieve).toHaveBeenCalledOnce()
    expect(retrieve.mock.calls[0]![1]).toBe(initial.id)
    expect(retrieve.mock.calls[0]![0]).toMatchObject({
      name: '未保存的修改',
      channels: { shortVideo: { conditions: { period: '7d' } } },
    })
    expect(save).not.toHaveBeenCalled()
    expect((await service.strategies())[0]).toEqual({
      ...initial,
      latestResult: '演示获取 4 项',
    })
    expect(
      wrapper.findComponent(StrategyDrawer).emitted('retrieved'),
    ).toHaveLength(1)
    expect(
      wrapper.findComponent(StrategyDrawer).emitted('saved'),
    ).toBeUndefined()
    expect(name.props('modelValue')).toBe('未保存的修改')
    expect(wrapper.findAllComponents(AppRadio)[0]!.props('modelValue')).toBe(
      '7d',
    )
    wrapper.unmount()
    queryClient.clear()
  })
  it('retrieves an unsaved draft without creating a strategy or emitting a saved-result refresh', async () => {
    const service = createSelectionMockHandlers()
    const before = await service.strategies()
    const retrieve = vi.spyOn(service, 'retrieve')
    const save = vi.spyOn(service, 'saveStrategy')
    const { wrapper, queryClient } = render(service)
    wrapper
      .findComponent(ShopStub)
      .vm.$emit('update:modelValue', before[0]!.shopId)
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '立即获取')!
      .trigger('click')
    await flushPromises()

    expect(retrieve).toHaveBeenCalledOnce()
    expect(retrieve.mock.calls[0]![1]).toBeUndefined()
    expect(save).not.toHaveBeenCalled()
    expect(await service.strategies()).toEqual(before)
    expect(
      wrapper.findComponent(StrategyDrawer).emitted('saved'),
    ).toBeUndefined()
    expect(
      wrapper.findComponent(StrategyDrawer).emitted('retrieved'),
    ).toBeUndefined()
    wrapper.unmount()
    queryClient.clear()
  })
  it('does not refresh recent results when retrieval fails', async () => {
    const service = createSelectionMockHandlers()
    const initial = (await service.strategies())[0]!
    service.retrieve = vi.fn().mockRejectedValue(new Error('获取失败'))
    const { wrapper, queryClient } = render(service, initial)
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '立即获取')!
      .trigger('click')
    await flushPromises()

    expect((await service.strategies())[0]).toEqual(initial)
    expect(
      wrapper.findComponent(StrategyDrawer).emitted('retrieved'),
    ).toBeUndefined()
    wrapper.unmount()
    queryClient.clear()
  })
  it('uses four mutually exclusive date options, retains disabled/collapsed values and never saves a preview range', async () => {
    const service = createSelectionMockHandlers()
    const initial = (await service.strategies())[0]!
    initial.channels.baiying.selected = true
    const save = vi.spyOn(service, 'saveStrategy')
    const preview = vi.spyOn(service, 'previewPeriod')
    const { wrapper, queryClient } = render(service, initial)
    const radio = wrapper.findAllComponents(AppRadio)[0]!
    expect(radio.props('options').map((option) => option.value)).toEqual([
      'realtime',
      '1d',
      '7d',
      '30d',
    ])
    for (const period of ['realtime', '1d', '7d', '30d']) {
      radio.vm.$emit('update:modelValue', period)
      await flushPromises()
      expect(radio.props('modelValue')).toBe(period)
      expect(wrapper.text()).not.toContain('Mock 示例区间')
      expect(preview).toHaveBeenLastCalledWith(period)
    }
    expect(wrapper.findComponent(NTooltip).exists()).toBe(true)
    const checkbox = wrapper.findAllComponents(AppCheckbox)[0]!
    checkbox.vm.$emit('update:modelValue', false)
    await flushPromises()
    expect(radio.props('disabled')).toBe(true)
    expect(radio.props('modelValue')).toBe('30d')
    const header = wrapper.findAll('.n-collapse-item__header-main')[0]!
    await header.trigger('click')
    await header.trigger('click')
    checkbox.vm.$emit('update:modelValue', true)
    await flushPromises()
    expect(radio.props('modelValue')).toBe('30d')
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '保存策略')!
      .trigger('click')
    await flushPromises()
    const conditions = save.mock.calls[0]![0].channels.shortVideo.conditions
    expect(conditions.period).toBe('30d')
    expect(Object.keys(conditions)).not.toContain('rangeLabel')
    expect(initial.channels.shortVideo.conditions.period).toBe('realtime')
    wrapper.unmount()
    queryClient.clear()
  })
  it('collapsing channels preserves values; saving detaches draft and includes both channels with only one schedule', async () => {
    const service = createSelectionMockHandlers()
    const initial = (await service.strategies())[0]!
    initial.channels.shortVideo.conditions.priceMode = 'custom'
    initial.channels.shortVideo.conditions.priceAbove = 0
    initial.channels.shortVideo.conditions.priceBelow = 50
    initial.scheduled = true
    initial.scheduleKind = 'daily'
    initial.dailyTime = '10:00'
    const save = vi.spyOn(service, 'saveStrategy')
    const { wrapper, queryClient } = render(service, initial)
    await flushPromises()
    wrapper
      .findComponent(CategorySelector)
      .vm.$emit('update:modelValue', 'shop-fixture-001/clothing/*')
    const header = wrapper.findAll('.n-collapse-item__header-main')[0]!
    await header.trigger('click')
    wrapper
      .findAllComponents(AppCheckbox)[1]!
      .vm.$emit('update:modelValue', true)
    await flushPromises()
    await header.trigger('click')
    expect(wrapper.findComponent(CategorySelector).props('modelValue')).toBe(
      'shop-fixture-001/clothing/*',
    )
    expect(initial.channels.shortVideo.conditions.categoryId).toBeNull()
    expect(initial.channels.baiying.selected).toBe(false)
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '保存策略')!
      .trigger('click')
    await flushPromises()
    expect(save).toHaveBeenCalledOnce()
    const draft = save.mock.calls[0]![0]
    expect(draft.channels.shortVideo.conditions.priceAbove).toBe(0)
    expect(draft.channels.baiying).toEqual({ selected: true, conditions: {} })
    expect(draft.dailyTime).toBe('10:00')
    expect(draft.scheduleKind).toBe('daily')
    wrapper.unmount()
    queryClient.clear()
  })
  it('clears old category and ignores an older shop response arriving last', async () => {
    let finishOld!: (nodes: CategoryNode[]) => void
    const service = createSelectionMockHandlers()
    service.categories = vi.fn((shop) =>
      shop === 'old'
        ? new Promise<CategoryNode[]>((resolve) => {
            finishOld = resolve
          })
        : Promise.resolve([{ id: 'new/category', name: '新店类目' }]),
    )
    const { wrapper, queryClient } = render(service)
    const shop = wrapper.findComponent(ShopStub)
    shop.vm.$emit('update:modelValue', 'old')
    await flushPromises()
    wrapper
      .findComponent(CategorySelector)
      .vm.$emit('update:modelValue', 'old/category')
    shop.vm.$emit('update:modelValue', 'new')
    await flushPromises()
    expect(
      wrapper.findComponent(CategorySelector).props('modelValue'),
    ).toBeNull()
    finishOld([{ id: 'old/category', name: '旧店类目' }])
    await flushPromises()
    expect(wrapper.findComponent(CategorySelector).props('nodes')).toEqual([
      { id: 'new/category', name: '新店类目' },
    ])
    wrapper.unmount()
    queryClient.clear()
  })
  it('shows explicit category error and retries rather than claiming an empty tree', async () => {
    const service = createSelectionMockHandlers()
    service.categories = vi
      .fn()
      .mockRejectedValueOnce(new Error('类目加载失败'))
      .mockResolvedValue([{ id: 'ready', name: '已恢复' }])
    const { wrapper, queryClient } = render(service)
    wrapper
      .findComponent(ShopStub)
      .vm.$emit('update:modelValue', 'shop-fixture-001')
    await flushPromises()
    expect(wrapper.text()).toContain('类目加载失败')
    const button = wrapper
      .findAll('button')
      .find((button) => button.text() === '重新加载')!
    await button.trigger('click')
    await flushPromises()
    expect(
      wrapper.findComponent(CategorySelector).props('nodes')[0]?.name,
    ).toBe('已恢复')
    wrapper.unmount()
    queryClient.clear()
  })
})
