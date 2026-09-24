import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import OperatingDashboardFilterBar from './OperatingDashboardFilterBar.vue'

describe('OperatingDashboardFilterBar', () => {
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
})
