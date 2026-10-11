import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ShopListTable from './ShopListTable.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import type { ShopListItemViewModel } from '@/entities/shop'
import type { ShopLoginFeedback } from '../model/useShopLogin'

const DataTable = defineComponent({
  props: ['columns', 'data'],
  setup(props) {
    return () =>
      h(
        'div',
        props.columns
          .find((column: { key?: string }) => column.key === 'actions')
          .render(props.data[0]),
      )
  },
})
const shop = {
  shopId: 'shop',
  platform: 'douyin',
  enabled: true,
} as ShopListItemViewModel

describe('shop list uses the shared login feedback, not an independent busy state', () => {
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
