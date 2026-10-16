import { defineComponent, h, reactive, ref } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { NMessageProvider } from 'naive-ui'
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
