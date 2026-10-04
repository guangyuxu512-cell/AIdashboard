import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { afterEach, expect, it, vi } from 'vitest'

import { useThemeStore } from '@/stores/theme'
import OperatingDashboardTrendChart from './OperatingDashboardTrendChart.vue'

const chart = vi.hoisted(() => ({
  setOption: vi.fn(),
  resize: vi.fn(),
  dispose: vi.fn(),
}))
vi.mock('echarts/core', () => ({ init: () => chart, use: vi.fn() }))

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

it('updates existing chart colors on light-to-light switches without changing zero/null data or recreating the chart', async () => {
  setActivePinia(createPinia())
  window.localStorage.clear()
  const store = useThemeStore()
  store.initialize()
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      disconnect() {}
    },
  )
  // Browser tests check actual CSS palettes; here isolate the reactive CSS read.
  vi.spyOn(window, 'getComputedStyle').mockImplementation(
    () =>
      ({
        getPropertyValue: (name: string) => `${store.resolvedPreset}:${name}`,
      }) as CSSStyleDeclaration,
  )
  const wrapper = mount(OperatingDashboardTrendChart, {
    props: {
      title: '成交趋势',
      metric: 'turnover',
      points: [
        { businessDate: '2026-09-19', turnoverCents: 0, orderCount: 0 },
        { businessDate: '2026-09-20', turnoverCents: null, orderCount: null },
      ],
    },
    global: {
      stubs: {
        PageSection: { template: '<div><slot /></div>' },
        AppRadio: true,
      },
    },
  })
  await nextTick()
  for (const preset of ['forest', 'coral', 'midnight'] as const) {
    store.setMode(preset)
    await nextTick()
    const option = chart.setOption.mock.lastCall?.[0]
    expect(option.series[0].lineStyle.color).toBe(`${preset}:--chart-primary`)
    expect(option.tooltip.textStyle.color).toBe(`${preset}:--text-primary`)
    expect(option.series[0].data).toEqual([0, null])
    expect(option.series[0].connectNulls).toBe(false)
    expect(option.series[0].areaStyle.opacity).toBe(0.08)
    expect(chart.dispose).not.toHaveBeenCalled()
  }
  wrapper.unmount()
  expect(chart.dispose).toHaveBeenCalledOnce()
})
