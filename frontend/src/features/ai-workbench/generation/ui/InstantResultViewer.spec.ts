import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { createInstantExecutionView } from '../model/instant-execution'
import InstantResultCard from './InstantResultCard.vue'
import InstantResultViewer from './InstantResultViewer.vue'

describe('InstantResultViewer', () => {
  it('renders the formal empty state before generation', () => {
    const wrapper = mount(InstantResultViewer, {
      props: { execution: null },
      global: { stubs: { teleport: true } },
    })
    expect(
      wrapper.get('[data-testid="instant-execution-summary"]').text(),
    ).toContain('执行结果')
    expect(wrapper.text()).toContain('暂无生成结果')
    expect(wrapper.find('[data-testid="instant-result-card"]').exists()).toBe(
      false,
    )
  })

  it('renders one fixed card for each four-state result', () => {
    const execution = createInstantExecutionView({
      id: 'viewer-execution',
      results: (['SUCCESS', 'RUNNING', 'WAITING', 'FAILED'] as const).map(
        (status, slotIndex) => ({
          id: `result-${slotIndex}`,
          slotIndex,
          name: `结果 ${slotIndex + 1}`,
          status,
          ...(status === 'SUCCESS' ? { previewUrl: 'preview' } : {}),
        }),
      ),
    })
    const wrapper = mount(InstantResultViewer, {
      props: { execution },
      global: { stubs: { teleport: true } },
    })
    const cards = wrapper.findAll('[data-testid="instant-result-card"]')
    expect(cards).toHaveLength(4)
    expect(cards.map((card) => card.attributes('data-result-status'))).toEqual([
      'SUCCESS',
      'RUNNING',
      'WAITING',
      'FAILED',
    ])
    expect(cards.map((card) => card.attributes('data-slot-index'))).toEqual([
      '0',
      '1',
      '2',
      '3',
    ])
  })

  it('keeps successful results focused on download without material archive UI', () => {
    const result = {
      id: 'success-result',
      slotIndex: 0,
      name: '生成结果-01.webp',
      status: 'SUCCESS' as const,
      previewUrl: 'preview',
    }
    const wrapper = mount(InstantResultCard, {
      props: { result },
      global: { stubs: { teleport: true } },
    })
    expect(wrapper.find('[aria-label="下载 生成结果-01.webp"]').exists()).toBe(
      true,
    )
    expect(wrapper.text()).not.toContain('素材库')
    expect(wrapper.find('[aria-label^="更多操作"]').exists()).toBe(false)
  })
})
