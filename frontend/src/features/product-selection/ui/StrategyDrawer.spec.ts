import { flushPromises, mount } from '@vue/test-utils'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { defineComponent, h } from 'vue'
import { NMessageProvider } from 'naive-ui'
import { describe, expect, it, vi } from 'vitest'
import { createSelectionMockHandlers } from '../api/selection-mock-handlers'
import type { CategoryNode, SelectionService } from '../model/contracts'
import CategorySelector from './CategorySelector.vue'
import StrategyDrawer from './StrategyDrawer.vue'

const ShopStub = defineComponent({
  name: 'ShopSelector',
  props: ['modelValue'],
  emits: ['update:modelValue'],
  template: '<div />',
})
function render(service: SelectionService) {
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
              strategy: null,
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
