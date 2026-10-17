import { defineComponent, h, nextTick, reactive, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { NAlert, NMessageProvider } from 'naive-ui'
import ShopConnectionSection from './ShopConnectionSection.vue'
import AppButton from '@/shared/ui/AppButton.vue'
import { shopLoginKey, type ShopLoginFeedback } from '../model/useShopLogin'
import type { ShopListItemViewModel } from '@/entities/shop'
import {
  ShopSessionStatusTag,
  shopSessionDataSource,
  shopSessionQueryKeys,
  type ShopSessionMetadataViewModel,
} from '@/entities/shop-session'
import ErrorState from '@/shared/components/ErrorState.vue'
import LoadingState from '@/shared/components/LoadingState.vue'

const queryState = vi.hoisted(() => ({
  pending: false,
  error: null as Error | null,
  realSessionQuery: false,
  credentialRefetch: vi.fn(),
}))

vi.mock('@/entities/credential', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  useShopCredentialQuery: () => ({
    data: { value: { configured: false } },
    isPending: { value: queryState.pending },
    error: { value: queryState.error },
    refetch: queryState.credentialRefetch,
  }),
  useCreateCredentialMutation: () => ({ isPending: { value: false } }),
  useUpdateCredentialMutation: () => ({ isPending: { value: false } }),
}))
vi.mock('@/entities/shop-session', async (importOriginal) => {
  const original =
    await importOriginal<typeof import('@/entities/shop-session')>()
  return {
    ...original,
    useShopSessionQuery: (
      ...args: Parameters<typeof original.useShopSessionQuery>
    ) =>
      queryState.realSessionQuery
        ? original.useShopSessionQuery(...args)
        : {
            data: { value: { configured: true, status: 'valid', version: 4 } },
            isPending: { value: false },
            error: { value: null },
          },
    useValidateShopSessionMutation: () => ({ isPending: { value: false } }),
  }
})

const shop = {
  shopId: 'shop',
  platform: 'douyin',
  shopName: 'Synthetic target',
  loginStatus: 'valid',
} as ShopListItemViewModel

beforeEach(() => {
  vi.clearAllMocks()
  queryState.pending = false
  queryState.error = null
  queryState.realSessionQuery = false
  queryState.credentialRefetch.mockResolvedValue(undefined)
})
afterEach(() => vi.restoreAllMocks())

describe('shop detail retains the fixed login and cancellation entries', () => {
  it.each([true, false])(
    'retains the actual cached-query error and reload action, with saved receipt=%s',
    async (withReceipt) => {
      queryState.realSessionQuery = true
      const client = new QueryClient({
        defaultOptions: {
          queries: {
            retry: false,
            refetchOnWindowFocus: false,
            gcTime: Infinity,
          },
        },
      })
      const cached: ShopSessionMetadataViewModel = {
        sessionId: 'session',
        configured: true,
        status: 'valid',
        version: 3,
        sourceDeviceId: null,
        sourceDeviceName: null,
        capturedAtDisplay: '2026-10-10 15:00',
        validatedAtDisplay: '2026-10-10 15:01',
        expiresAtDisplay: null,
        refreshInProgress: false,
        refreshLeaseExpiresAtDisplay: null,
      }
      const read = vi
        .spyOn(shopSessionDataSource, 'getForShop')
        .mockResolvedValue(cached)
      const feedback = reactive(new Map<string, ShopLoginFeedback>())
      const login = vi.fn()
      const wrapper = mount(
        defineComponent({
          setup: () => () =>
            h(NMessageProvider, null, {
              default: () => h(ShopConnectionSection, { shop }),
            }),
        }),
        {
          global: {
            plugins: [[VueQueryPlugin, { queryClient: client }]],
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
        await flushPromises()
        expect(wrapper.text()).toContain('v3')
        expect(read).toHaveBeenCalledTimes(1)
        read.mockRejectedValue(new Error('synthetic metadata read failed'))
        await expect(
          client.invalidateQueries(
            { queryKey: shopSessionQueryKeys.shop('shop') },
            { throwOnError: true },
          ),
        ).rejects.toThrow('synthetic metadata read failed')
        const status =
          '本次登录已更新（v4 · 2026-10-11 17:01）；店铺信息刷新未完成，请刷新列表'
        if (withReceipt)
          feedback.set('shop', {
            busy: false,
            opening: false,
            error: null,
            status,
            success: {
              sessionVersion: 4,
              validatedAt: '2026-10-11T09:01:00Z',
              readRefreshFailed: true,
            },
          })
        await flushPromises()
        expect(client.getQueryData(shopSessionQueryKeys.shop('shop'))).toEqual(
          cached,
        )
        expect(
          client.getQueryState(shopSessionQueryKeys.shop('shop'))?.status,
        ).toBe('error')
        expect(wrapper.findComponent(ErrorState).exists()).toBe(true)
        expect(wrapper.findComponent(ErrorState).props('description')).toBe(
          'synthetic metadata read failed',
        )
        expect(wrapper.find('.shop-session-card__metadata').exists()).toBe(
          false,
        )
        expect(wrapper.text()).not.toContain(cached.validatedAtDisplay)
        const alerts = wrapper.findAllComponents(NAlert)
        expect(alerts).toHaveLength(withReceipt ? 1 : 0)
        if (withReceipt) {
          expect(alerts[0]!.props('type')).toBe('warning')
          expect(alerts[0]!.text()).toContain(status)
        }
        read.mockResolvedValue({ ...cached, version: 4 })
        await wrapper.findComponent(ErrorState).find('button').trigger('click')
        await flushPromises()
        expect(read).toHaveBeenCalledTimes(3)
        expect(queryState.credentialRefetch).toHaveBeenCalledTimes(1)
        expect(wrapper.findComponent(ErrorState).exists()).toBe(false)
        expect(login).not.toHaveBeenCalled()
      } finally {
        wrapper.unmount()
        client.clear()
      }
    },
  )
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
              success: identityMismatch
                ? {
                    sessionVersion: 4,
                    validatedAt: '2026-10-11T09:01:00Z',
                    readRefreshFailed: true,
                  }
                : undefined,
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
      expect(wrapper.findAllComponents(NAlert)).toHaveLength(
        identityMismatch ? 1 : 0,
      )
      if (identityMismatch)
        expect(wrapper.findComponent(NAlert).props('type')).toBe('error')
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
