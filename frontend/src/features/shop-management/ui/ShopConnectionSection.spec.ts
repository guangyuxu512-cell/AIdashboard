import { defineComponent, h, nextTick, reactive, ref } from 'vue'
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NAlert, NMessageProvider } from 'naive-ui'
import ShopConnectionSection from './ShopConnectionSection.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import { shopLoginKey, type ShopLoginFeedback } from '../model/useShopLogin'
import type { ShopListItemViewModel } from '@/entities/shop'
import { ShopSessionStatusTag } from '@/entities/shop-session'
import ErrorState from '@/shared/components/ErrorState.vue'
import LoadingState from '@/shared/components/LoadingState.vue'

const queryState = vi.hoisted(() => ({
  pending: false,
  error: null as Error | null,
}))

vi.mock('@/entities/credential', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  useShopCredentialQuery: () => ({
    data: { value: { configured: false } },
    isPending: { value: queryState.pending },
    error: { value: queryState.error },
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

const shop = {
  shopId: 'shop',
  platform: 'douyin',
  shopName: 'Synthetic target',
  loginStatus: 'valid',
} as ShopListItemViewModel

beforeEach(() => {
  queryState.pending = false
  queryState.error = null
})

describe('shop detail retains the fixed login and cancellation entries', () => {
  it.each([
    ['loading', true],
    ['query-error', true],
    ['loading', false],
    ['query-error', false],
  ] as const)(
    'shows only current mismatch feedback during %s (identityMismatch=%s), never cached Session data as fresh',
    async (phase, identityMismatch) => {
      queryState.pending = phase === 'loading'
      queryState.error =
        phase === 'query-error' ? new Error('synthetic metadata failure') : null
      const error = identityMismatch
        ? '目标店铺：Synthetic target。本次登录店铺不符，原登录状态保留'
        : '本次验证未完成'
      const feedback = reactive(
        new Map<string, ShopLoginFeedback>([
          [
            'shop',
            {
              busy: true,
              opening: false,
              identityMismatch,
              error,
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
                login: vi.fn(),
                cancel: vi.fn(),
              },
            },
            stubs: { CredentialFormDialog: true },
          },
        },
      )
      expect(wrapper.findComponent(NAlert).exists()).toBe(identityMismatch)
      if (identityMismatch)
        expect(wrapper.findComponent(NAlert).text()).toBe(error)
      expect(wrapper.findComponent(ErrorState).exists()).toBe(
        phase === 'query-error',
      )
      expect(wrapper.findComponent(LoadingState).exists()).toBe(
        phase === 'loading',
      )
      expect(wrapper.findComponent(ShopSessionStatusTag).exists()).toBe(false)
      expect(wrapper.text()).not.toContain('v4')
      if (phase === 'query-error')
        expect(wrapper.findComponent(ErrorState).props('retryable')).toBe(true)
      feedback.delete('shop')
      await nextTick()
      expect(wrapper.findComponent(NAlert).exists()).toBe(false)
      expect(wrapper.findComponent(ErrorState).exists()).toBe(
        phase === 'query-error',
      )
      expect(wrapper.findComponent(LoadingState).exists()).toBe(
        phase === 'loading',
      )
      wrapper.unmount()
    },
  )
  it('shows the current target mismatch in the existing alert while preserving the real valid Session', async () => {
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
              login: vi.fn(),
              cancel: vi.fn(),
            },
          },
          stubs: { CredentialFormDialog: true },
        },
      },
    )
    expect(wrapper.findComponent(NAlert).props('type')).toBe('error')
    expect(wrapper.findAllComponents(NAlert)).toHaveLength(1)
    expect(wrapper.findComponent(NAlert).text()).toBe(error)
    expect(wrapper.findComponent(ShopSessionStatusTag).props('status')).toBe(
      'valid',
    )
    expect(wrapper.text()).toContain('v4')
    expect(wrapper.text()).not.toContain('已更新')
    await nextTick()
    expect(wrapper.findComponent(NAlert).text()).toBe(error)
    feedback.delete('shop')
    await nextTick()
    expect(wrapper.findComponent(NAlert).exists()).toBe(false)
    expect(wrapper.findComponent(ShopSessionStatusTag).props('status')).toBe(
      'valid',
    )
    expect(wrapper.text()).toContain('v4')
    wrapper.unmount()
  })
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
