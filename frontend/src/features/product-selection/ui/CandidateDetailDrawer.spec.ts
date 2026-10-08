import { flushPromises, mount } from '@vue/test-utils'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { describe, expect, it } from 'vitest'
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
    const wrapper = mount(CandidateDetailDrawer, {
      props: { id: 'candidate-000', service, contextKey: 'actor:team' },
      global: {
        plugins: [[VueQueryPlugin, { queryClient }]],
        stubs: {
          DetailDrawer: { template: '<div><slot /></div>' },
          ExternalProductImage: true,
        },
      },
    })
    await flushPromises()
    const row = await service.candidate('candidate-000')
    expect(wrapper.findComponent(ExternalProductImage).props('src')).toBe(
      row.imageUrl,
    )
    for (const label of [
      '图片',
      '店铺',
      '类目',
      '价格带',
      '上架日期',
      '差评率',
      '屏蔽状态',
      '来源',
      '统计周期',
      '榜单排名',
      '首次上榜',
    ])
      expect(wrapper.text()).toContain(label)
    expect(wrapper.text()).toContain('已屏蔽')
    expect(wrapper.text()).toContain(row.shopName)
    expect(wrapper.text()).toContain('9087654321098765000')
    expect(wrapper.text()).toContain('1000–5000')
    expect(wrapper.text()).toContain('100–500')
    expect(wrapper.text()).toContain('—')
    await wrapper.setProps({ id: 'candidate-005' })
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
})
