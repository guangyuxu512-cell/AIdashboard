import { mount } from '@vue/test-utils'
import { NDropdown } from 'naive-ui'
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

  it('names the material action explicitly and replaces it after save', async () => {
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
    const dropdown = wrapper.getComponent(NDropdown)
    expect(dropdown.props('options')).toEqual([
      { key: 'save-to-assets', label: '保存到素材库' },
    ])
    await dropdown.vm.$emit('select', 'save-to-assets')
    expect(wrapper.emitted('save')?.[0]).toEqual([result])

    await wrapper.setProps({
      result: { ...result, savedToProductId: 'pmg-phone-stand' },
    })
    expect(wrapper.text()).toContain('已加入素材库')
    expect(wrapper.findComponent(NDropdown).exists()).toBe(false)
  })

  it('shows the material membership in record-only result cards', () => {
    const wrapper = mount(InstantResultCard, {
      props: {
        result: {
          id: 'unsaved-result',
          slotIndex: 0,
          status: 'SUCCESS',
          previewUrl: 'preview',
        },
        showActions: false,
        showAssetLibraryStatus: true,
      },
      global: { stubs: { teleport: true } },
    })
    expect(wrapper.text()).toContain('未加入素材库')
    expect(wrapper.findComponent(NDropdown).exists()).toBe(false)
  })
})
