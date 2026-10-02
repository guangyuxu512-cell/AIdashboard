import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import OperatingDashboardFilterBar from './OperatingDashboardFilterBar.vue'

describe('OperatingDashboardFilterBar', () => {
  it('guides the first selected range to ordinary update, not an inferred operating date', () => {
    const wrapper = mount(OperatingDashboardFilterBar, {
      props: {
        modelValue: {
          datePreset: 'last7Days',
          customDateRange: null,
          shopId: 'shop-1',
          platform: 'douyin',
        },
        shopOptions: [],
        platformOptions: [],
        refreshAvailable: true,
        coverage: {
          state: 'available',
          supportedShopCount: 1,
          collectedShopDays: 0,
          totalShopDays: 7,
          missingShopDays: 7,
          missingSamplesTruncated: false,
          manualBackfillRequired: true,
          missingSamples: [
            {
              shopId: 'shop-1',
              shopName: '新店',
              businessDate: '2026-09-22',
              state: 'missing',
              failureReason: null,
            },
          ],
        },
      },
      global: {
        stubs: {
          FilterBar: {
            template: '<div><slot /><slot name="primary-action" /></div>',
          },
          FilterField: { template: '<div><slot /></div>' },
          AppButton: { template: '<button><slot /></button>' },
          AppRadio: true,
          AppSelect: true,
          NDropdown: true,
          NTooltip: { template: '<div><slot name="trigger" /></div>' },
        },
      },
    })
    expect(wrapper.text()).toContain('所选范围尚未采集，请点击更新数据')
    expect(wrapper.text()).not.toContain('超过最近30日')
    wrapper.unmount()
  })
  it('shows only the server-mapped safe reason for a failed coverage sample', () => {
    const wrapper = mount(OperatingDashboardFilterBar, {
      props: {
        modelValue: {
          datePreset: 'yesterday',
          customDateRange: null,
          shopId: null,
          platform: null,
        },
        shopOptions: [],
        platformOptions: [],
        refreshAvailable: false,
        coverage: {
          state: 'available',
          supportedShopCount: 1,
          collectedShopDays: 0,
          totalShopDays: 1,
          missingShopDays: 1,
          missingSamples: [
            {
              shopId: 'shop-1',
              shopName: '测试店铺',
              businessDate: '2026-09-22',
              state: 'failed',
              failureReason: '抖店经营数据响应无效',
            },
          ],
          missingSamplesTruncated: false,
          manualBackfillRequired: false,
        },
      },
      global: {
        stubs: {
          FilterBar: {
            template: '<div><slot /><slot name="primary-action" /></div>',
          },
          FilterField: { template: '<div><slot /></div>' },
          AppButton: { template: '<button><slot /></button>' },
          AppRadio: true,
          AppSelect: true,
          NTooltip: {
            template: '<div><slot name="trigger" /><slot /></div>',
          },
        },
      },
    })

    expect(wrapper.text()).toContain('查看缺失')
    // Naive's tooltip body is teleported, so assert the computed text passed
    // to it rather than relying on the overlay to be mounted in jsdom.
    expect(
      (wrapper.vm as unknown as { coverageDetail: string }).coverageDetail,
    ).toBe('测试店铺 · 2026-09-22 · 采集失败（抖店经营数据响应无效）')
  })

  it('distinguishes a known platform-metric unknown from a collection failure', () => {
    const wrapper = mount(OperatingDashboardFilterBar, {
      props: {
        modelValue: {
          datePreset: 'yesterday',
          customDateRange: null,
          shopId: null,
          platform: null,
        },
        shopOptions: [],
        platformOptions: [],
        refreshAvailable: false,
        coverage: {
          state: 'available',
          supportedShopCount: 1,
          collectedShopDays: 0,
          totalShopDays: 1,
          missingShopDays: 1,
          missingSamples: [
            {
              shopId: 'shop-1',
              shopName: '测试店铺',
              businessDate: '2026-09-22',
              state: 'unknown',
              failureReason: '抖店平台未提供可确认的经营指标值',
            },
          ],
          missingSamplesTruncated: false,
          manualBackfillRequired: false,
        },
      },
      global: {
        stubs: {
          FilterBar: {
            template: '<div><slot /><slot name="primary-action" /></div>',
          },
          FilterField: { template: '<div><slot /></div>' },
          AppButton: { template: '<button><slot /></button>' },
          AppRadio: true,
          AppSelect: true,
          NTooltip: {
            template: '<div><slot name="trigger" /><slot /></div>',
          },
        },
      },
    })

    expect(
      (wrapper.vm as unknown as { coverageDetail: string }).coverageDetail,
    ).toBe(
      '测试店铺 · 2026-09-22 · 平台指标未知（抖店平台未提供可确认的经营指标值）',
    )
  })

  it('shows a durable pre-boundary wait without calling it a platform failure', () => {
    const wrapper = mount(OperatingDashboardFilterBar, {
      props: {
        modelValue: {
          datePreset: 'yesterday',
          customDateRange: null,
          shopId: null,
          platform: null,
        },
        shopOptions: [],
        platformOptions: [],
        refreshAvailable: false,
        coverage: {
          state: 'available',
          supportedShopCount: 1,
          collectedShopDays: 0,
          totalShopDays: 1,
          missingShopDays: 1,
          missingSamples: [
            {
              shopId: 'shop-1',
              shopName: '测试店铺',
              businessDate: '2026-09-23',
              state: 'waiting_collection_time',
              failureReason: '等待每日采集时间后再请求平台',
            },
          ],
          missingSamplesTruncated: false,
          manualBackfillRequired: false,
        },
      },
      global: {
        stubs: {
          FilterBar: {
            template: '<div><slot /><slot name="primary-action" /></div>',
          },
          FilterField: { template: '<div><slot /></div>' },
          AppButton: { template: '<button><slot /></button>' },
          AppRadio: true,
          AppSelect: true,
          NTooltip: {
            template: '<div><slot name="trigger" /><slot /></div>',
          },
        },
      },
    })

    expect(
      (wrapper.vm as unknown as { coverageDetail: string }).coverageDetail,
    ).toBe(
      '测试店铺 · 2026-09-23 · 等待每日采集时间（等待每日采集时间后再请求平台）',
    )
  })

  it('distinguishes a confirmed pre-operation range from missing collection', () => {
    const wrapper = mount(OperatingDashboardFilterBar, {
      props: {
        modelValue: {
          datePreset: 'last30Days',
          customDateRange: null,
          shopId: 'shop-1',
          platform: 'douyin',
        },
        shopOptions: [],
        platformOptions: [],
        refreshAvailable: true,
        coverage: {
          state: 'available',
          supportedShopCount: 1,
          collectedShopDays: 0,
          totalShopDays: 0,
          missingShopDays: 0,
          missingSamples: [],
          missingSamplesTruncated: false,
          manualBackfillRequired: false,
          notOperatingShopDays: 30,
          shopsWithUnknownOperatingStart: 0,
          noOperatingScope: true,
        },
      },
      global: {
        stubs: {
          FilterBar: {
            template: '<div><slot /><slot name="primary-action" /></div>',
          },
          FilterField: { template: '<div><slot /></div>' },
          AppButton: { template: '<button><slot /></button>' },
          AppRadio: true,
          AppSelect: true,
          NDropdown: { template: '<div><slot /></div>' },
        },
      },
    })

    expect(wrapper.text()).toContain('该范围尚未经营')
    expect(wrapper.text()).not.toContain('0/30 个应采店铺日期')
  })
})
