import { flushPromises, mount } from '@vue/test-utils'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { NMessageProvider } from 'naive-ui'
import { defineComponent, h, ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { AppInput } from '@/shared/ui'
import { createSelectionMockHandlers } from '../api/selection-mock-handlers'
import StrategyDrawer from './StrategyDrawer.vue'

describe('paused selection strategy', () => {
  it('shows the historical shop as read-only without requesting its category', async () => {
    const service = createSelectionMockHandlers()
    const strategy = (await service.strategies())[0]!
    service.categories = vi.fn()
    service.manual = { capabilities: vi.fn(), submit: vi.fn() }
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const show = ref(true)
    const wrapper = mount(defineComponent({ setup: () => () => h(NMessageProvider, {}, {
      default: () => h(StrategyDrawer, { show: show.value, strategy, service, contextKey: 'actor:team',
        capabilities: { execution_enabled: false, unavailable_reason: 'EXECUTION_DISABLED',
          manual_execution_available: false, strategy_save_available: false, schedule_available: false } }),
    }) }), { global: { plugins: [[VueQueryPlugin, { queryClient }]],
      stubs: { AppDrawer: { template: '<div><slot /><slot name="footer" /></div>' } } } })
    await flushPromises()
    const shopInput = wrapper.findAllComponents(AppInput)[0]!
    expect(shopInput.props('modelValue')).toBe(strategy.shopName)
    expect(shopInput.props('disabled')).toBe(true)
    expect(service.categories).not.toHaveBeenCalled()
    expect(service.manual!.submit).not.toHaveBeenCalled()
    wrapper.unmount()
    queryClient.clear()
  })
})
