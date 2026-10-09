import { flushPromises, mount } from '@vue/test-utils'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { describe, expect, it, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { NDescriptions, NMessageProvider } from 'naive-ui'
import { AppButton } from '@/shared/ui'
import { createSelectionMockHandlers } from '../api/selection-mock-handlers'
import {
  formatCandidateDate,
  formatReviewRate,
} from '../model/candidate-display'
import CandidateDetailDrawer from './CandidateDetailDrawer.vue'
import ExternalProductImage from './ExternalProductImage.vue'

describe('candidate details preserve the draft contract', () => {
  it('shows identity, missing metrics, block state and raw ranges with the existing preview', async () => {
    const service = createSelectionMockHandlers()
    await service.demoAction('candidate-000', 'block')
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    })
    const selectedId = ref('candidate-000')
    const Wrapper = defineComponent({
      setup: () => () =>
        h(
          NMessageProvider,
          {},
          {
            default: () =>
              h(CandidateDetailDrawer, {
                id: selectedId.value,
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
          DetailDrawer: {
            template: '<div><slot /><slot name="footer" /></div>',
          },
          ExternalProductImage: true,
        },
      },
    })
    await flushPromises()
    const row = await service.candidate('candidate-000')
    expect(
      wrapper
        .findAll('section')
        .map((section) => section.attributes('aria-label')),
    ).toEqual([
      '罗盘视频榜单数据',
      '排名与发现信息',
      '商品基础信息',
      '请求来源信息',
    ])
    const metrics = wrapper.get('section[aria-label="罗盘视频榜单数据"]')
    expect(metrics.findComponent(NDescriptions).props('column')).toBe(2)
    expect(metrics.text()).toContain(row.sourceContext.statisticalPeriod)
    expect(
      metrics.findAll('.candidate-detail__metric').map((item) => item.text()),
    ).toEqual(['—', '1000–5000', '100–500', '10–50'])
    expect(wrapper.findComponent(ExternalProductImage).props('src')).toBe(
      row.imageUrl,
    )
    for (const label of [
      '商品所属商家',
      '请求罗盘使用的自有店铺',
      '类目',
      '价格带',
      '上架日期',
      '差评率',
      '屏蔽状态',
      '来源',
      '统计周期',
      '本次排名',
      '首次上榜',
    ])
      expect(wrapper.text()).toContain(label)
    expect(wrapper.text()).toContain('已屏蔽')
    expect(wrapper.text()).toContain(row.shopName)
    expect(wrapper.text()).toContain(row.merchant!.name)
    expect(wrapper.text()).toContain('9087654321098765000')
    expect(wrapper.text()).toContain('1000–5000')
    expect(wrapper.text()).toContain('100–500')
    expect(wrapper.text()).toContain('—')
    const marker = vi.spyOn(service, 'markCompetitor')
    await wrapper
      .findAllComponents(AppButton)
      .find((button) => button.text() === '标记为竞品店铺')!
      .trigger('click')
    await flushPromises()
    expect(marker).toHaveBeenCalledExactlyOnceWith(row.merchant!.shopId)
    expect(wrapper.text()).toContain('已标记竞品店铺')
    expect(
      wrapper
        .findAllComponents(AppButton)
        .find((button) => button.text() === '采集资料')!
        .props('tone'),
    ).toBe('primary')
    expect(
      wrapper
        .findAllComponents(AppButton)
        .find((button) => button.text() === '更新罗盘指标')!
        .props('tone'),
    ).toBe('secondary')
    selectedId.value = 'candidate-005'
    await flushPromises()
    expect(wrapper.text()).toContain('0.00%')
    expect(wrapper.text()).toContain('1万–5万')
    expect(wrapper.text()).toContain('单位未确认')
    wrapper.unmount()
    queryClient.clear()
    expect(formatCandidateDate(null)).toBe('—')
    expect(formatReviewRate(null)).toBe('—')
    expect(formatReviewRate(0)).toBe('0.00%')
  })
  it('does not enable competitor marking when the product merchant is unknown, even with a valid request shop', async () => {
    const fixture =
      await createSelectionMockHandlers().candidate('candidate-000')
    const service = createSelectionMockHandlers([
      { ...fixture, merchant: null },
    ])
    const marker = vi.spyOn(service, 'markCompetitor')
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    })
    const wrapper = mount(
      defineComponent({
        setup: () => () =>
          h(
            NMessageProvider,
            {},
            {
              default: () =>
                h(CandidateDetailDrawer, {
                  id: fixture.id,
                  service,
                  contextKey: 'actor:team',
                }),
            },
          ),
      }),
      {
        global: {
          plugins: [[VueQueryPlugin, { queryClient }]],
          stubs: {
            DetailDrawer: {
              template: '<div><slot /><slot name="footer" /></div>',
            },
            ExternalProductImage: true,
          },
        },
      },
    )
    await flushPromises()
    const button = wrapper
      .findAllComponents(AppButton)
      .find((button) => button.text() === '标记为竞品店铺')!
    expect(button.props('disabled')).toBe(true)
    expect(wrapper.text()).toContain('商品商家身份未确认')
    expect(wrapper.text()).toContain(fixture.shopName)
    button.vm.$emit('click', new MouseEvent('click'))
    await flushPromises()
    expect(marker).not.toHaveBeenCalled()
    wrapper.unmount()
    queryClient.clear()
  })
})
