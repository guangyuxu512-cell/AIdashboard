import { mount } from '@vue/test-utils'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

import { AppPage, MobileListToolbar, MobileSummaryStrip } from '@/shared/ui'

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
    expect(wrapper.get('dl').classes()).toContain('mobile-section-surface')
    expect(wrapper.get('dl').classes()).not.toContain('mobile-card')
    expect(wrapper.find('button').exists()).toBe(false)
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
    expect(wrapper.findAll('.mobile-list-toolbar__control')).toHaveLength(2)
  })

  it('centralizes compact layout sizes and hides scrollbars without disabling scroll', () => {
    const tokens = readFileSync(
      resolve(process.cwd(), 'src/shared/styles/tokens.css'),
      'utf8',
    )
    const base = readFileSync(
      resolve(process.cwd(), 'src/shared/styles/base.css'),
      'utf8',
    )

    expect(tokens).toContain('--layout-summary-height: 64px')
    expect(tokens).toContain('--layout-toolbar-height: 44px')
    expect(tokens).toContain('--control-height-compact: 32px')
    expect(tokens).toContain('--touch-target-min: 44px')
    expect(base).toContain('scrollbar-width: none')
    expect(base).toContain('-ms-overflow-style: none')
    expect(base).toContain('.mobile-scroll-container::-webkit-scrollbar')
    expect(base).not.toMatch(
      /\.mobile-scroll-container\s*\{[^}]*overflow:\s*hidden/s,
    )
  })

  it('gives Detail content a named keyboard scroll entry', async () => {
    const wrapper = mount(AppPage, {
      props: { label: '设备详情内容' },
      slots: { default: '<p>详情</p>' },
    })

    expect(wrapper.attributes()).toMatchObject({
      role: 'region',
      'aria-label': '设备详情内容',
      tabindex: '0',
    })
    expect(wrapper.classes()).toContain('mobile-scroll-container')

    Object.defineProperty(wrapper.element, 'clientHeight', {
      configurable: true,
      value: 200,
    })
    await wrapper.trigger('keydown', { key: 'PageDown' })
    expect(wrapper.element.scrollTop).toBe(160)
    await wrapper.trigger('keydown', { key: 'PageUp' })
    expect(wrapper.element.scrollTop).toBe(0)
  })
})
