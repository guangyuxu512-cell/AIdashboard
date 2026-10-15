import { mount } from '@vue/test-utils'
import {
  NButton,
  NConfigProvider,
  NInput,
  NPagination,
  NSelect,
} from 'naive-ui'
import type { GlobalThemeOverrides } from 'naive-ui'
import { defineComponent, h, nextTick, ref } from 'vue'
import { afterAll, beforeAll, describe, expect, it } from 'vitest'

import { AppButton, AppInput, AppSelect } from '@/shared/ui'
import { createListDensityTheme } from '@/shared/ui/list-density'
import type { ListDensity } from '@/shared/ui/list-density'
import FilterBar from './FilterBar.vue'
import ManagementListSection from './ManagementListSection.vue'
import PageSection from './PageSection.vue'
import PaginationBar from './PaginationBar.vue'
import TableToolbar from './TableToolbar.vue'

describe('explicit list density', () => {
  beforeAll(() =>
    document.documentElement.style.setProperty(
      '--list-compact-control-height',
      '28px',
    ),
  )
  afterAll(() =>
    document.documentElement.style.removeProperty(
      '--list-compact-control-height',
    ),
  )
  it('resolves numeric menu height from its token, rejecting missing or zero values', () => {
    for (const height of ['31px', '29.5px']) {
      document.documentElement.style.setProperty(
        '--list-compact-control-height',
        height,
      )
      expect(
        createListDensityTheme('compact')?.Select?.peers?.InternalSelectMenu
          ?.optionHeightMedium,
      ).toBe(height)
    }
    for (const height of ['', '0px', '-2px', 'var(--missing)', '28']) {
      document.documentElement.style.setProperty(
        '--list-compact-control-height',
        height,
      )
      expect(() => createListDensityTheme('compact')).toThrow(
        'Missing pixel token: --list-compact-control-height',
      )
      expect(createListDensityTheme('default')).toBeUndefined()
    }
    document.documentElement.style.setProperty(
      '--list-compact-control-height',
      '28px',
    )
  })

  it('keeps existing roots, attrs, fill and default inherited theme', () => {
    const wrapper = mount(PageSection, {
      props: { fill: true },
      attrs: { class: 'existing-consumer', 'aria-label': '列表' },
      slots: { default: () => h(AppButton, {}, () => '默认操作') },
    })
    expect(wrapper.element.tagName).toBe('SECTION')
    expect(wrapper.classes()).toEqual(
      expect.arrayContaining(['existing-consumer', 'page-section--fill']),
    )
    expect(wrapper.classes()).not.toContain('page-section--compact')
    expect(wrapper.attributes('aria-label')).toBe('列表')
    expect(wrapper.find('.n-config-provider').exists()).toBe(false)
    expect(
      wrapper.findComponent(NConfigProvider).props('themeOverrides'),
    ).toBeUndefined()
    expect(wrapper.findComponent(NConfigProvider).props('abstract')).toBe(true)
    wrapper.unmount()
  })

  it('sizes filter fields and both action slots, without changing control contracts', () => {
    const wrapper = mount(FilterBar, {
      props: { density: 'compact' },
      slots: {
        default: () => [
          h(AppInput, { modelValue: 'query' }),
          h(AppSelect, { options: [] }),
        ],
        actions: () => h(AppButton, {}, () => '重置'),
        'primary-action': () => h(AppButton, { tone: 'primary' }, () => '查询'),
      },
    })
    expect(wrapper.classes()).toContain('filter-bar--compact')
    expect(wrapper.findComponent(NInput).props()).toMatchObject({
      value: 'query',
      size: 'medium',
    })
    expect(wrapper.findComponent(NSelect).props('size')).toBe('medium')
    const buttons = wrapper.findAllComponents(NButton)
    expect(buttons).toHaveLength(2)
    for (const button of buttons) {
      expect(button.element.getAttribute('style')).toContain(
        '--n-height: var(--list-compact-control-height)',
      )
    }
    wrapper.unmount()
  })

  it('does not mutate its parent and reacts to parent theme or density changes', async () => {
    const original: GlobalThemeOverrides = {
      Button: {
        heightMedium: '34px',
        fontSizeMedium: '14px',
        textColorPrimary: 'white',
        colorPrimary: 'green',
      },
      Select: { peers: { InternalSelection: { textColor: 'black' } } },
    }
    Object.freeze(original.Button)
    Object.freeze(original.Select!.peers!.InternalSelection)
    Object.freeze(original.Select!.peers)
    Object.freeze(original.Select)
    Object.freeze(original)
    const before = JSON.stringify(original)
    const theme = ref<GlobalThemeOverrides>(original)
    const density = ref<ListDensity>('compact')
    const wrapper = mount(
      defineComponent({
        setup: () => () =>
          h(
            NConfigProvider,
            { abstract: true, themeOverrides: theme.value },
            {
              default: () => [
                h(
                  PageSection,
                  { density: density.value },
                  {
                    default: () =>
                      h(
                        AppButton,
                        { tone: 'primary', class: 'scoped' },
                        () => '列表',
                      ),
                  },
                ),
                h(
                  AppButton,
                  { tone: 'primary', class: 'unscoped' },
                  () => '其他页面',
                ),
              ],
            },
          ),
      }),
    )
    const style = (selector: string) =>
      wrapper.get(selector).attributes('style')
    expect(style('.scoped')).toContain(
      '--n-height: var(--list-compact-control-height)',
    )
    expect(style('.unscoped')).toContain('--n-height: 34px')
    expect(style('.scoped')).toContain('--n-color: green')
    theme.value = {
      ...original,
      Button: { ...original.Button, colorPrimary: 'teal' },
    }
    await nextTick()
    expect(style('.scoped')).toContain('--n-color: teal')
    expect(style('.unscoped')).toContain('--n-color: teal')
    density.value = 'default'
    await nextTick()
    expect(style('.scoped')).toContain('--n-height: 34px')
    expect(style('.scoped')).toContain('--n-font-size: 14px')
    expect(JSON.stringify(original)).toBe(before)
    expect(createListDensityTheme('compact')).not.toHaveProperty('common')
    expect(
      createListDensityTheme('compact')?.Select?.peers?.InternalSelectMenu
        ?.optionHeightMedium,
    ).toBe('28px')
    wrapper.unmount()
  })

  it('forwards compact list density and retains pagination events and page sizes', () => {
    const section = mount(ManagementListSection, {
      props: { density: 'compact' },
    })
    expect(section.findComponent(PageSection).props()).toMatchObject({
      density: 'compact',
      fill: true,
    })
    expect(
      section.find('.management-list-section__content--compact').exists(),
    ).toBe(true)
    const toolbar = mount(TableToolbar, {
      props: { density: 'compact' },
      slots: { actions: () => h(AppButton, {}, () => '批量操作') },
    })
    expect(toolbar.get('button').attributes('style')).toContain(
      '--n-height: var(--list-compact-control-height)',
    )
    const pagination = mount(PaginationBar, {
      props: { density: 'compact', page: 1, pageSize: 10, itemCount: 40 },
    })
    const control = pagination.findComponent(NPagination)
    expect(control.props('pageSizes')).toEqual([10, 20, 50, 100])
    control.vm.$emit('update:page', 2)
    control.vm.$emit('update:pageSize', 20)
    expect(pagination.emitted('update:page')).toEqual([[2]])
    expect(pagination.emitted('update:pageSize')).toEqual([[20]])
    section.unmount()
    toolbar.unmount()
    pagination.unmount()
  })
})
