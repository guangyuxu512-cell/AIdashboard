import { defineComponent, h, reactive, ref } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { NAlert, NMessageProvider } from 'naive-ui'
import ShopConnectionSection from './ShopConnectionSection.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import { shopLoginKey, type ShopLoginFeedback } from '../model/useShopLogin'
import type { ShopListItemViewModel } from '@/entities/shop'

vi.mock('@/entities/credential', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  useShopCredentialQuery: () => ({
    data: { value: { configured: false } },
    isPending: { value: false },
    error: { value: null },
  }),
  useCreateCredentialMutation: () => ({ isPending: { value: false } }),
  useUpdateCredentialMutation: () => ({ isPending: { value: false } }),
}))
vi.mock('@/entities/shop-session', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  useShopSessionQuery: () => ({
    data: { value: { configured: true, status: 'valid', version: 4 } },
    isPending: { value: false },
    error: { value: null },
  }),
  useValidateShopSessionMutation: () => ({ isPending: { value: false } }),
}))

const shop = { shopId: 'shop', platform: 'douyin' } as ShopListItemViewModel

describe('shop detail retains the fixed login and cancellation entries', () => {
  it.each([false, true])(
    'shows the current saved result without a recovery lock, readRefreshFailed=%s',
    async (readRefreshFailed) => {
      const status =
        '本次登录已更新（v4 · 2026-10-11 17:01）' +
        (readRefreshFailed ? '；店铺信息刷新未完成，请刷新列表' : '')
      const login = vi.fn()
      const feedback = reactive(
        new Map<string, ShopLoginFeedback>([
          [
            'shop',
            {
              busy: false,
              opening: false,
              error: null,
              status,
              success: {
                sessionVersion: 4,
                validatedAt: '2026-10-11T09:01:00Z',
                readRefreshFailed,
              },
            },
          ],
        ]),
      )
      const wrapper = mount(
        defineComponent({
          setup: () => () =>
            h(NMessageProvider, null, {
              default: () => h(ShopConnectionSection, { shop }),
            }),
        }),
        {
          global: {
            provide: {
              [shopLoginKey as symbol]: {
                canLogin: ref(true),
                feedback,
                login,
              },
            },
            stubs: { CredentialFormDialog: true },
          },
        },
      )
      try {
        expect(wrapper.findComponent(NAlert).props('type')).toBe(
          readRefreshFailed ? 'warning' : 'success',
        )
        expect(wrapper.findComponent(NAlert).text()).toContain(status)
        const buttons = wrapper.findAllComponents(AppButton)
        expect(
          buttons
            .find((button) => button.text() === '验证会话')!
            .props('disabled'),
        ).toBe(false)
        expect(buttons.some((button) => button.text() === '取消登录')).toBe(
          false,
        )
        const button = buttons.find((item) => item.text() === '登录')!
        expect(button.props('disabled')).toBe(false)
        await button.trigger('click')
        expect(login).toHaveBeenCalledExactlyOnceWith(shop)
      } finally {
        wrapper.unmount()
      }
    },
  )
  it.each([true, false])(
    'login remains clickable with canContinue=%s and uses the shared flow',
    async (canContinue) => {
      const login = vi.fn()
      const cancel = vi.fn()
      const feedback = reactive(
        new Map<string, ShopLoginFeedback>([
          [
            'shop',
            {
              busy: true,
              opening: false,
              retryReady: canContinue,
              retryBlocked: !canContinue,
              error: canContinue
                ? '请点击登录继续验证'
                : '次数已用尽，请取消后重新登录',
              status: null,
            },
          ],
        ]),
      )
      const wrapper = mount(
        defineComponent({
          setup: () => () =>
            h(NMessageProvider, null, {
              default: () => h(ShopConnectionSection, { shop }),
            }),
        }),
        {
          global: {
            provide: {
              [shopLoginKey as symbol]: {
                canLogin: ref(true),
                feedback,
                login,
                cancel,
              },
            },
            stubs: { CredentialFormDialog: true },
          },
        },
      )
      const button = wrapper
        .findAllComponents(AppButton)
        .find((item) => item.text() === '登录')!
      expect(button.props('disabled')).toBe(false)
      expect(button.props('loading')).toBe(false)
      await button.trigger('click')
      expect(login).toHaveBeenCalledExactlyOnceWith(shop)
      expect(wrapper.text()).toContain(feedback.get('shop')!.error)
      const cancelling = wrapper
        .findAllComponents(AppButton)
        .find((item) => item.text() === '取消登录')!
      await cancelling.trigger('click')
      expect(cancel).toHaveBeenCalledExactlyOnceWith('shop')
      wrapper.unmount()
    },
  )
})
