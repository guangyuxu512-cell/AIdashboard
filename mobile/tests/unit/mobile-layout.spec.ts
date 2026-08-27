import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import { MobileListToolbar, MobileSummaryStrip } from '@/shared/ui'

describe('Mobile Layout shared components', () => {
  it('renders two to four summary metrics through one stable surface', () => {
    const wrapper = mount(MobileSummaryStrip, {
      props: {
        ariaLabel: '设备总览',
        busy: true,
        items: [
          { key: 'online', label: '在线设备', value: 3, tone: 'success' },
          { key: 'running', label: '运行中', value: 1, tone: 'primary' },
          { key: 'offline', label: '离线设备', value: 1, tone: 'muted' },
        ],
      },
    })

    expect(wrapper.attributes('aria-label')).toBe('设备总览')
    expect(wrapper.get('dl').attributes('aria-busy')).toBe('true')
    expect(wrapper.findAll('.mobile-summary-strip__item')).toHaveLength(3)
    expect(wrapper.get('[data-testid="summary-online"]').text()).toBe('3')
    expect(wrapper.get('[data-testid="summary-running"]').text()).toBe('1')
    expect(wrapper.get('[data-testid="summary-offline"]').text()).toBe('1')
    expect(wrapper.get('[data-testid="summary-online"]').classes()).toEqual([])
    expect(
      wrapper
        .get('[data-testid="summary-online"]')
        .element.parentElement?.classList.contains(
          'mobile-summary-strip__item--success',
        ),
    ).toBe(true)
  })

  it('keeps title, meta, selector and filter in one toolbar contract', async () => {
    const wrapper = mount(MobileListToolbar, {
      props: {
        title: '任务',
        meta: '54 个',
        selectorLabel: '全部',
        selectorAriaLabel: '选择任务状态，当前全部',
        filterLabel: '筛选',
      },
    })

    expect(wrapper.findAll('[data-testid="mobile-list-toolbar"]')).toHaveLength(
      1,
    )
    expect(wrapper.get('h1').text()).toBe('任务')
    expect(wrapper.text()).toContain('54 个')
    expect(
      wrapper
        .get('[data-testid="mobile-list-selector"]')
        .attributes('aria-label'),
    ).toBe('选择任务状态，当前全部')
    expect(
      wrapper
        .get('[data-testid="mobile-list-filter"]')
        .attributes('aria-label'),
    ).toBe('筛选')

    await wrapper.get('[data-testid="mobile-list-selector"]').trigger('click')
    await wrapper.get('[data-testid="mobile-list-filter"]').trigger('click')
    expect(wrapper.emitted('selector')).toHaveLength(1)
    expect(wrapper.emitted('filter')).toHaveLength(1)
  })
})
