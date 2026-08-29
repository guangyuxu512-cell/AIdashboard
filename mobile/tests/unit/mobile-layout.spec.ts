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
        meta: '54个',
        selectorLabel: '全部',
        selectorAriaLabel: '选择任务状态，当前全部',
        filterLabel: '筛选',
      },
    })

    expect(wrapper.findAll('[data-testid="mobile-list-toolbar"]')).toHaveLength(
      1,
    )
    const toolbar = wrapper.get('[data-testid="mobile-list-toolbar"]')
    const identity = wrapper.get('.mobile-list-toolbar__identity')
    const actions = wrapper.get('.mobile-list-toolbar__actions')

    expect(toolbar.classes()).not.toContain('mobile-card')
    expect(
      Array.from(toolbar.element.children).map((element) => element.className),
    ).toEqual(['mobile-list-toolbar__identity', 'mobile-list-toolbar__actions'])
    expect(
      Array.from(identity.element.children).map((element) => element.tagName),
    ).toEqual(['H1', 'SPAN'])
    expect(wrapper.get('h1').text()).toBe('任务')
    expect(identity.text()).toBe('任务54个')
    expect(
      Array.from(actions.element.children).map((element) =>
        element.getAttribute('data-testid'),
      ),
    ).toEqual(['mobile-list-selector', 'mobile-list-filter'])
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
    const vantTheme = readFileSync(
      resolve(process.cwd(), 'src/shared/styles/vant-theme.css'),
      'utf8',
    )
    const deviceCard = readFileSync(
      resolve(
        process.cwd(),
        'src/features/device-center/ui/DeviceListCard.vue',
      ),
      'utf8',
    )
    const taskCard = readFileSync(
      resolve(process.cwd(), 'src/entities/task/ui/TaskListCard.vue'),
      'utf8',
    )
    const runtimeSummary = readFileSync(
      resolve(
        process.cwd(),
        'src/features/device-center/ui/DeviceRuntimeSummary.vue',
      ),
      'utf8',
    )
    const taskDetail = readFileSync(
      resolve(process.cwd(), 'src/pages/tasks/TaskDetailPage.vue'),
      'utf8',
    )
    const runtimeLog = readFileSync(
      resolve(process.cwd(), 'src/features/task-runtime/ui/TaskRuntimeLog.vue'),
      'utf8',
    )
    const capabilityPanel = readFileSync(
      resolve(
        process.cwd(),
        'src/features/device-center/ui/DeviceCapabilityPanel.vue',
      ),
      'utf8',
    )
    const toolbar = readFileSync(
      resolve(process.cwd(), 'src/shared/ui/MobileListToolbar.vue'),
      'utf8',
    )
    const summaryStrip = readFileSync(
      resolve(process.cwd(), 'src/shared/ui/MobileSummaryStrip.vue'),
      'utf8',
    )

    expect(tokens).toContain('--layout-header-height: 52px')
    expect(tokens).toContain('--layout-detail-header-height: 50px')
    expect(tokens).toContain('--layout-summary-height: 96px')
    expect(tokens).toContain('--layout-summary-padding-y: 8px')
    expect(tokens).toContain('--layout-toolbar-height: 44px')
    expect(tokens).toContain('--layout-bottom-nav-height: 58px')
    expect(tokens).toContain('--layout-page-padding-x: 16px')
    expect(tokens).toContain('--layout-page-padding-y: 12px')
    expect(tokens).toContain('--layout-section-gap: 12px')
    expect(tokens).toContain('--layout-card-gap: 8px')
    expect(tokens).toContain('--layout-card-padding-x: 12px')
    expect(tokens).toContain('--layout-card-padding-y: 16px')
    expect(tokens).not.toContain('--layout-card-padding:')
    expect(tokens).toContain('--layout-card-row-gap: 4px')
    expect(tokens).toContain('--layout-capability-panel-height: 354px')
    expect(tokens).toContain('--layout-capability-row-min-height: 48px')
    expect(tokens).toContain('--control-height-compact: 30px')
    expect(tokens).toContain('--control-size-icon-button: 34px')
    expect(tokens).toContain('--touch-target-min: 44px')
    expect(tokens).toContain('--icon-size-default: 22px')
    expect(tokens).toContain('--icon-size-small: 16px')
    expect(tokens).toContain('--icon-size-card-leading: 28px')
    expect(tokens).toContain('--icon-size-card-chevron: 16px')
    expect(tokens).toContain('--icon-size-runtime-summary: 22px')
    expect(tokens).toContain('--icon-size-summary-metric: 20px')
    expect(tokens).toContain('--icon-size-capability-row: 16px')
    expect(tokens).toContain('--layout-card-leading-icon-slot-width: 44px')
    expect(tokens).toContain('--layout-card-trailing-icon-slot-width: 24px')
    expect(tokens).toContain('--layout-runtime-summary-padding-x: 12px')
    expect(tokens).toContain('--layout-runtime-summary-padding-y: 16px')
    expect(tokens).toContain('--layout-runtime-summary-icon-slot-width: 36px')
    expect(tokens).toContain('--layout-capability-icon-slot-width: 28px')
    expect(tokens).toContain('--font-size-caption: 12px')
    expect(tokens).toContain('--font-size-secondary: 13px')
    expect(tokens).toContain('--font-size-action: 13px')
    expect(tokens).toContain('--font-size-body: 14px')
    expect(tokens).toContain('--font-size-label: 15px')
    expect(tokens).toContain('--font-size-title: 16px')
    expect(tokens).toContain('--font-size-display: 18px')
    expect(tokens).toContain('--line-height-caption: 16px')
    expect(tokens).toContain('--line-height-secondary: 18px')
    expect(tokens).toContain('--line-height-action: 18px')
    expect(tokens).toContain('--line-height-body: 20px')
    expect(tokens).toContain('--line-height-label: 20px')
    expect(tokens).toContain('--line-height-title: 22px')
    expect(tokens).toContain('--line-height-display: 22px')
    expect(tokens).toContain('--font-weight-bold: 700')
    expect(vantTheme).toContain(
      '--van-button-default-font-size: var(--font-size-action)',
    )
    expect(vantTheme).toContain(
      '--van-button-default-height: var(--control-height-default)',
    )
    expect(vantTheme).toContain(
      '--van-tabbar-item-line-height: var(--line-height-caption)',
    )
    expect(vantTheme).toContain('--van-tab-font-size: var(--font-size-action)')
    expect(vantTheme).toMatch(
      /\.van-nav-bar\s*\{\s*line-height:\s*var\(--line-height-title\)/s,
    )
    for (const card of [deviceCard, taskCard]) {
      expect(card).toContain('column-gap: var(--space-2)')
      expect(card).toContain(
        'padding: var(--layout-card-padding-y) var(--layout-card-padding-x)',
      )
      expect(card).toContain('gap: var(--layout-card-row-gap)')
      expect(card).toContain(
        'width: var(--layout-card-leading-icon-slot-width)',
      )
      expect(card).toContain('font-size: var(--icon-size-card-leading)')
      expect(card).toContain(
        'width: var(--layout-card-trailing-icon-slot-width)',
      )
      expect(card).toContain('font-size: var(--icon-size-card-chevron)')
    }
    expect(summaryStrip).toContain('padding: var(--layout-summary-padding-y)')
    expect(summaryStrip).toContain('height: 100%')
    expect(runtimeSummary).toContain(
      'padding: var(--layout-runtime-summary-padding-y)',
    )
    expect(runtimeSummary).toContain('var(--layout-runtime-summary-padding-x)')
    expect(runtimeSummary).toContain('column-gap: var(--space-2)')
    expect(runtimeSummary).toContain(
      'margin-inline: var(--layout-runtime-summary-padding-x)',
    )
    expect(runtimeSummary).toContain(
      'width: var(--layout-runtime-summary-icon-slot-width)',
    )
    expect(runtimeSummary).toContain(
      'font-size: var(--icon-size-runtime-summary)',
    )
    expect(runtimeSummary).not.toMatch(
      /\.device-runtime-summary\s*\{[^}]*\n\s*(?:min-|max-)?height\s*:/s,
    )
    expect(taskDetail).not.toMatch(
      /\.task-detail-page__summary\s*\{[^}]*\n\s*(?:min-|max-)?height\s*:/s,
    )
    expect(taskDetail).not.toMatch(
      /\.task-detail-page__core\s*\{[^}]*\n\s*(?:min-|max-)?height\s*:/s,
    )
    expect(runtimeLog).not.toMatch(
      /\.runtime-log\s*\{[^}]*\n\s*(?:min-|max-)?height\s*:/s,
    )
    expect(capabilityPanel).toContain(
      'width: var(--layout-capability-icon-slot-width)',
    )
    expect(capabilityPanel).toContain(
      'font-size: var(--icon-size-capability-row)',
    )
    expect(capabilityPanel).toContain('min-width: var(--touch-target-min)')
    expect(capabilityPanel).toContain('height: var(--touch-target-min)')
    expect(capabilityPanel).toContain(
      'height: var(--control-height-capability-action)',
    )
    expect(toolbar).toContain('min-width: var(--touch-target-min)')
    expect(toolbar).toContain('height: var(--touch-target-min)')
    expect(toolbar).toContain('height: var(--control-height-compact)')
    expect(base).toContain('width: var(--touch-target-min)')
    expect(base).toContain('height: var(--touch-target-min)')
    expect(base).toContain('--control-size-icon-button')
    expect(summaryStrip).toContain('width: var(--icon-size-summary-metric)')
    expect(summaryStrip).toContain('height: var(--icon-size-summary-metric)')
    expect(summaryStrip).toContain('font-size: var(--icon-size-summary-metric)')
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
