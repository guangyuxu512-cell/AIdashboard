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
          {
            key: 'online',
            label: '在线设备',
            value: 3,
            icon: 'desktop-o',
            tone: 'success',
          },
          {
            key: 'running',
            label: '运行中',
            value: 1,
            icon: 'play-circle-o',
            tone: 'primary',
          },
          {
            key: 'offline',
            label: '离线设备',
            value: 1,
            icon: 'close',
            tone: 'muted',
          },
        ],
      },
    })

    expect(wrapper.attributes('aria-label')).toBe('设备总览')
    expect(wrapper.get('ul').attributes('aria-busy')).toBe('true')
    expect(wrapper.get('ul').classes()).toContain('mobile-section-surface')
    expect(wrapper.get('ul').classes()).not.toContain('mobile-card')
    expect(wrapper.find('button').exists()).toBe(false)
    expect(wrapper.findAll('.mobile-summary-strip__item')).toHaveLength(3)
    expect(
      wrapper
        .findAll('.mobile-summary-strip__label')
        .map((item) => item.text()),
    ).toEqual(['在线设备', '运行中', '离线设备'])
    expect(wrapper.findAll('.mobile-summary-strip__icon')).toHaveLength(3)
    expect(wrapper.get('[data-testid="summary-online"]').text()).toBe('3')
    expect(wrapper.get('[data-testid="summary-running"]').text()).toBe('1')
    expect(wrapper.get('[data-testid="summary-offline"]').text()).toBe('1')
    expect(wrapper.get('[data-testid="summary-online"]').classes()).toEqual([
      'mobile-summary-strip__value',
    ])
    expect(
      wrapper
        .get('[data-testid="summary-online"]')
        .element.closest('.mobile-summary-strip__item')
        ?.classList.contains('mobile-summary-strip__item--success'),
    ).toBe(true)
  })

  it('supports optional interactive metrics without changing their anatomy', async () => {
    const wrapper = mount(MobileSummaryStrip, {
      props: {
        items: [
          {
            key: 'online',
            label: '在线设备',
            value: 3,
            icon: 'desktop-o',
            interactive: true,
            selected: true,
            ariaLabel: '在线设备，当前筛选，点击恢复全部',
          },
          {
            key: 'running',
            label: '运行中',
            value: 1,
            icon: 'play-circle-o',
            interactive: true,
            selected: false,
          },
          {
            key: 'offline',
            label: '离线设备',
            value: '—',
            icon: 'close',
            interactive: true,
            selected: false,
            disabled: true,
          },
        ],
      },
    })

    const buttons = wrapper.findAll(
      '.mobile-summary-strip__metric--interactive',
    )
    expect(buttons).toHaveLength(3)
    expect(buttons[0]?.element.tagName).toBe('BUTTON')
    expect(buttons[0]?.attributes()).toMatchObject({
      type: 'button',
      'aria-pressed': 'true',
      'aria-label': '在线设备，当前筛选，点击恢复全部',
    })
    expect(buttons[1]?.attributes('aria-pressed')).toBe('false')
    expect(buttons[2]?.attributes()).toHaveProperty('disabled')
    expect(buttons[0]?.find('.mobile-summary-strip__icon').exists()).toBe(true)
    expect(buttons[0]?.find('.mobile-summary-strip__value').text()).toBe('3')
    expect(buttons[0]?.find('.mobile-summary-strip__label').text()).toBe(
      '在线设备',
    )

    await buttons[0]?.trigger('click')
    await buttons[1]?.trigger('click')
    await buttons[2]?.trigger('click')
    expect(wrapper.emitted('select')).toEqual([['online'], ['running']])
  })

  it('keeps the same summary slots while metric values are unknown', () => {
    const wrapper = mount(MobileSummaryStrip, {
      props: {
        ariaLabel: '设备总览',
        busy: true,
        items: [
          {
            key: 'online',
            label: '在线设备',
            value: '—',
            icon: 'desktop-o',
          },
          {
            key: 'running',
            label: '运行中',
            value: '—',
            icon: 'play-circle-o',
          },
          {
            key: 'offline',
            label: '离线设备',
            value: '—',
            icon: 'close',
          },
        ],
      },
    })

    expect(wrapper.get('ul').attributes('aria-busy')).toBe('true')
    expect(wrapper.findAll('.mobile-summary-strip__item')).toHaveLength(3)
    expect(
      wrapper
        .findAll('.mobile-summary-strip__value')
        .map((item) => item.text()),
    ).toEqual(['—', '—', '—'])
    expect(
      wrapper
        .findAll('.mobile-summary-strip__label')
        .map((item) => item.text()),
    ).toEqual(['在线设备', '运行中', '离线设备'])
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

    expect(tokens).toContain('--layout-summary-height: 98px')
    expect(tokens).toContain('--layout-toolbar-height: 44px')
    expect(tokens).toContain('--control-height-compact: 32px')
    expect(tokens).toContain('--touch-target-min: 44px')
    expect(tokens).toContain('--font-size-caption: 12px')
    expect(tokens).toContain('--font-size-secondary: 13px')
    expect(tokens).toContain('--font-size-body: 14px')
    expect(tokens).toContain('--font-size-label: 15px')
    expect(tokens).toContain('--font-size-title: 16px')
    expect(tokens).toContain('--font-size-display: 18px')
    expect(tokens).toContain('--font-weight-bold: 700')
    expect(base).toContain('scrollbar-width: none')
    expect(base).toContain('-ms-overflow-style: none')
    expect(base).toContain('.mobile-scroll-container::-webkit-scrollbar')
    expect(base).not.toMatch(
      /\.mobile-scroll-container\s*\{[^}]*overflow:\s*hidden/s,
    )
    expect(base).toMatch(
      /h1,\s*h2,\s*h3,\s*strong,\s*b\s*\{\s*font-weight:\s*var\(--font-weight-semibold\)/s,
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
