import { defineComponent, h, nextTick, reactive, ref } from 'vue'
import { readFileSync } from 'node:fs'
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { darkTheme, NConfigProvider } from 'naive-ui'
import ShopListTable from './ShopListTable.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import StatusTag from '@/shared/components/StatusTag.vue'
import { ShopSessionStatusTag } from '@/entities/shop-session'
import type { ShopListItemViewModel } from '@/entities/shop'
import type { ShopLoginFeedback } from '../model/useShopLogin'
import { createNaiveThemeOverrides } from '@/app/providers/naive-theme'

const tokensCss = readFileSync('src/shared/styles/tokens.css', 'utf8')

const DataTable = defineComponent({
  props: ['columns', 'data', 'scrollX'],
  setup(props) {
    return () =>
      h(
        'div',
        ['loginStatus', 'actions'].map((key) =>
          h(
            'div',
            { 'data-column': key },
            props.columns
              .find((column: { key?: string }) => column.key === key)
              .render(props.data[0]),
          ),
        ),
      )
  },
})
const shop = {
  shopId: 'shop',
  platform: 'douyin',
  enabled: true,
  shopName: 'Synthetic target',
  loginStatus: 'valid',
} as ShopListItemViewModel

describe('shop list uses the shared login feedback, not an independent busy state', () => {
  it.each(['graphite', 'forest', 'coral', 'midnight'])(
    'reuses the same small status tag and column space for the current result in %s',
    async (preset) => {
      const style = document.createElement('style')
      style.textContent = tokensCss
      document.head.append(style)
      const previousTheme = document.documentElement.dataset.theme
      const previousPreset = document.documentElement.dataset.themePreset
      document.documentElement.dataset.theme =
        preset === 'midnight' ? 'dark' : 'light'
      document.documentElement.dataset.themePreset = preset
      const feedback = ref(new Map<string, ShopLoginFeedback>())
      const rows = ref([shop])
      const { Tag } = createNaiveThemeOverrides(preset)
      const wrapper = mount(NConfigProvider, {
        props: {
          theme: preset === 'midnight' ? darkTheme : null,
          themeOverrides: { Tag },
        },
        slots: {
          default: () =>
            h(ShopListTable, {
              rows: rows.value,
              canLogin: true,
              loginFeedback: feedback.value,
            }),
        },
        global: { stubs: { DataTable } },
      })
      try {
        const original = wrapper.get('[data-column="loginStatus"] .n-tag')
          .element as HTMLElement
        const height = original.style.getPropertyValue('--n-height')
        const fontSize = original.style.getPropertyValue('--n-font-size')
        expect(height).not.toBe('')
        expect(wrapper.get('[data-column="loginStatus"]').text()).toBe('有效')
        const status = '本次登录已更新（v4 · 2026-10-11 17:01）'
        feedback.value.set('shop', {
          busy: false,
          opening: false,
          error: null,
          status,
          success: {
            sessionVersion: 4,
            validatedAt: '2026-10-11T09:01:00Z',
            readRefreshFailed: false,
          },
        })
        await flushPromises()
        const current = wrapper.get('[data-column="loginStatus"] .n-tag')
          .element as HTMLElement
        expect(current.textContent).toBe('已更新')
        expect(current.getAttribute('aria-label')).toBe(status)
        expect(current.style.getPropertyValue('--n-height')).toBe(height)
        expect(current.style.getPropertyValue('--n-font-size')).toBe(fontSize)
        const columns = wrapper.findComponent(DataTable).props('columns')
        expect(
          columns.find(
            (column: { key?: string }) => column.key === 'loginStatus',
          ).width,
        ).toBe(96)
        expect(wrapper.findComponent(DataTable).props('scrollX')).toBe(1114)
        const order = wrapper
          .findAllComponents(AppButton)
          .map((button) => button.text())
        expect(order).toEqual(['查看', '登录', '停用', '移除'])
        feedback.value.set('shop', {
          busy: false,
          opening: false,
          error: null,
          status: status + '；店铺信息刷新未完成，请刷新列表',
          success: {
            sessionVersion: 4,
            validatedAt: '2026-10-11T09:01:00Z',
            readRefreshFailed: true,
          },
        })
        await flushPromises()
        expect(wrapper.get('[data-column="loginStatus"]').text()).toBe('已保存')
        expect(
          (
            wrapper.get('[data-column="loginStatus"] .n-tag')
              .element as HTMLElement
          ).style.getPropertyValue('--n-height'),
        ).toBe(height)
        rows.value = [{ ...shop, loginStatus: 'invalid' }]
        await flushPromises()
        expect(wrapper.get('[data-column="loginStatus"]').text()).toBe('已失效')
      } finally {
        wrapper.unmount()
        style.remove()
        if (previousTheme === undefined)
          delete document.documentElement.dataset.theme
        else document.documentElement.dataset.theme = previousTheme
        if (previousPreset === undefined)
          delete document.documentElement.dataset.themePreset
        else document.documentElement.dataset.themePreset = previousPreset
      }
    },
  )
  it('keeps wrong-shop feedback local and persistent without changing the valid Session or status-cell layout', async () => {
    const error =
      '目标店铺：Synthetic target。本次登录店铺不符，原登录状态保留；请切换正确账号后点击登录继续验证'
    const feedback = reactive(
      new Map<string, ShopLoginFeedback>([
        [
          'shop',
          {
            busy: true,
            opening: false,
            retryReady: true,
            identityMismatch: true,
            error,
            status: null,
          },
        ],
      ]),
    )
    const wrapper = mount(ShopListTable, {
      props: { rows: [shop], canLogin: true, loginFeedback: feedback },
      global: { stubs: { DataTable } },
    })
    const table = wrapper.findComponent(DataTable)
    expect(
      table
        .props('columns')
        .find((column: { key?: string }) => column.key === 'loginStatus').width,
    ).toBe(96)
    expect(table.props('scrollX')).toBe(1114)
    const warning = wrapper
      .findAllComponents(StatusTag)
      .find((tag) => tag.props('label') === '店铺不符')!
    expect(warning.props('tone')).toBe('warning')
    expect(warning.attributes('aria-label')).toBe(error)
    expect(wrapper.findComponent(ShopSessionStatusTag).exists()).toBe(false)
    expect(
      wrapper.findAllComponents(AppButton).map((button) => button.text()),
    ).toEqual(['查看', '登录', '停用', '移除'])
    expect(wrapper.text()).not.toContain('已更新')
    expect(shop.loginStatus).toBe('valid')
    await nextTick()
    expect(wrapper.text()).toContain('店铺不符')
    feedback.set('shop', {
      ...feedback.get('shop')!,
      success: {
        sessionVersion: 4,
        validatedAt: '2026-10-11T09:01:00Z',
        readRefreshFailed: true,
      },
    })
    await nextTick()
    expect(wrapper.text()).toContain('店铺不符')
    expect(wrapper.text()).not.toMatch(/已保存|已更新/)
    expect(
      wrapper
        .findAllComponents(StatusTag)
        .find((tag) => tag.props('label') === '店铺不符')!
        .attributes('aria-label'),
    ).toBe(error)
    feedback.delete('shop')
    await nextTick()
    expect(wrapper.findComponent(ShopSessionStatusTag).props('status')).toBe(
      'valid',
    )
    expect(wrapper.text()).not.toContain('店铺不符')
    wrapper.unmount()
  })
  it('keeps the fixed login entry usable for continuation or focus even when further validation is blocked', async () => {
    const wrapper = mount(ShopListTable, {
      props: {
        rows: [shop],
        canLogin: true,
        loginFeedback: new Map([
          [
            'shop',
            {
              busy: true,
              opening: false,
              retryReady: true,
              error: '请在原窗口完成登录',
              status: null,
            },
          ],
        ]),
      },
      global: { stubs: { DataTable } },
    })
    const action = wrapper
      .findAllComponents(AppButton)
      .find((button) => button.text() === '登录')!
    expect(action.props('disabled')).toBe(false)
    expect(action.props('loading')).toBe(false)
    await action.trigger('click')
    expect(wrapper.emitted('login')?.[0]).toEqual([shop])
    await wrapper.setProps({
      loginFeedback: new Map([
        [
          'shop',
          {
            busy: true,
            opening: false,
            retryReady: false,
            retryBlocked: true,
            error: '请取消后核对权限',
            status: null,
          },
        ],
      ]),
    })
    const blocked = wrapper
      .findAllComponents(AppButton)
      .find((button) => button.text() === '登录')!
    expect(blocked.props('disabled')).toBe(false)
    await blocked.trigger('click')
    expect(wrapper.emitted('login')).toHaveLength(2)
    wrapper.unmount()
  })
  it('restores the actual login button after native-close feedback is removed', async () => {
    const wrapper = mount(ShopListTable, {
      props: {
        rows: [shop],
        canLogin: true,
        loginFeedback: new Map([
          [
            'shop',
            {
              busy: true,
              opening: false,
              focusing: true,
              error: null,
              status: '等待识别',
            },
          ],
        ]),
      },
      global: { stubs: { DataTable } },
    })
    expect(wrapper.text()).toContain('登录中…')
    await wrapper.setProps({ loginFeedback: new Map() })
    const login = wrapper
      .findAllComponents(AppButton)
      .find((button) => button.text() === '登录')!
    expect(login.props('loading')).toBe(false)
    expect(login.find('button').attributes('disabled')).toBeUndefined()
    await login.trigger('click')
    expect(wrapper.emitted('login')?.[0]).toEqual([shop])
    wrapper.unmount()
  })
  it('opening/loading disables duplicate click then restores the same button after failure', async () => {
    const busy: ShopLoginFeedback = {
      busy: true,
      opening: true,
      error: null,
      status: '正在打开店铺登录窗口',
    }
    const wrapper = mount(ShopListTable, {
      props: {
        rows: [shop],
        canLogin: true,
        loginFeedback: new Map([['shop', busy]]),
      },
      global: { stubs: { DataTable } },
    })
    const login = () =>
      wrapper
        .findAllComponents(AppButton)
        .find((button) => /打开中|登录中|^登录$/.test(button.text()))!
    expect(login().props('loading')).toBe(true)
    expect(login().props('disabled')).toBe(true)
    expect(login().find('button').attributes('disabled')).toBeDefined()
    await login().trigger('click')
    expect(wrapper.emitted('login')).toBeUndefined()
    await wrapper.setProps({
      loginFeedback: new Map([
        [
          'shop',
          {
            busy: false,
            opening: false,
            error: '打开超时，请稍后重试',
            status: null,
          },
        ],
      ]),
    })
    expect(login().text()).toBe('登录')
    expect(login().props('loading')).toBe(false)
    expect(login().props('disabled')).toBe(false)
    await login().trigger('click')
    expect(wrapper.emitted('login')?.[0]).toEqual([shop])
    wrapper.unmount()
  })
  it('an opened capture keeps the same login button clickable for focus only; ordinary members do not gain the action', async () => {
    const wrapper = mount(ShopListTable, {
      props: {
        rows: [shop],
        canLogin: true,
        loginFeedback: new Map([
          [
            'shop',
            { busy: true, opening: false, error: null, status: '等待识别' },
          ],
        ]),
      },
      global: { stubs: { DataTable } },
    })
    expect(wrapper.text()).toContain('登录中…')
    const login = wrapper
      .findAllComponents(AppButton)
      .find((button) => button.text() === '登录中…')!
    expect(login.props('loading')).toBe(false)
    expect(login.props('disabled')).toBe(false)
    await login.trigger('click')
    expect(wrapper.emitted('login')?.[0]).toEqual([shop])
    await wrapper.setProps({
      loginFeedback: new Map([
        [
          'shop',
          {
            busy: true,
            opening: false,
            focusing: true,
            error: null,
            status: '等待识别',
          },
        ],
      ]),
    })
    expect(login.props('loading')).toBe(true)
    expect(login.props('disabled')).toBe(true)
    wrapper.unmount()
    const denied = mount(ShopListTable, {
      props: { rows: [shop], canLogin: false },
      global: { stubs: { DataTable } },
    })
    expect(denied.text()).not.toContain('登录')
    denied.unmount()
  })
})
