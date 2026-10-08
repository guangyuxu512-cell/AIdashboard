import { flushPromises, mount } from '@vue/test-utils'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { defineComponent, h } from 'vue'
import { NMessageProvider } from 'naive-ui'
import { describe, expect, it, vi } from 'vitest'
import { createSelectionMockHandlers } from '../api/selection-mock-handlers'
import type {
  CategoryNode,
  SelectionService,
  SelectionStrategy,
} from '../model/contracts'
import { AppCheckbox } from '@/shared/ui'
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
