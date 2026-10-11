import { defineComponent, h, reactive } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  useShopLogin,
  supportsShopLogin,
  validationFailureMessage,
} from './useShopLogin'
import { ApiError } from '@/shared/api'
import type { ShopListItemViewModel } from '@/entities/shop'

const state = vi.hoisted(() => ({
  auth: {
    isSuperAccount: true,
    activeTeamId: 'team',
    currentUser: { userId: 'person' },
  },
  invalidate: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
  warning: vi.fn(),
  info: vi.fn(),
  acquire: vi.fn(),
  release: vi.fn(),
  confirm: vi.fn(),
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => reactive(state.auth) }))
vi.mock('@tanstack/vue-query', () => ({
  useQueryClient: () => ({ invalidateQueries: state.invalidate }),
}))
vi.mock('naive-ui', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  useMessage: () => state,
}))
vi.mock('@/entities/shop-session', () => ({
  shopSessionQueryKeys: { shop: (id: string) => ['shop-sessions', 'shop', id] },
  shopSessionDataSource: {
    acquireRefreshLease: state.acquire,
    releaseRefreshLease: state.release,
    confirmRecovery: state.confirm,
  },
}))

const shop = {
  shopId: 'shop',
  platform: 'douyin',
  loginStatus: 'valid',
} as ShopListItemViewModel
function setup() {
  let flow!: ReturnType<typeof useShopLogin>
  const wrapper = mount(
    defineComponent({
      setup() {
        flow = useShopLogin()
        return () => h('div')
      },
    }),
  )
  return { flow, wrapper }
}
function bridge() {
  return {
    focusShop: vi.fn().mockResolvedValue(false),
    open: vi.fn().mockResolvedValue({ attemptId: 'attempt' }),
    getStatus: vi
      .fn()
      .mockResolvedValue({
        attemptId: 'attempt',
        status: 'identified',
        message: 'identified',
      }),
    refresh: vi
      .fn()
      .mockResolvedValue({
        shopId: 'shop',
        status: 'valid',
        sessionVersion: 4,
        validatedAt: '2026-10-11T09:01:00Z',
      }),
    close: vi.fn().mockResolvedValue(undefined),
    complete: vi.fn(),
  }
}
beforeEach(() => {
  vi.clearAllMocks()
  state.auth.isSuperAccount = true
  state.auth.activeTeamId = 'team'
  state.auth.currentUser = { userId: 'person' }
  state.invalidate.mockReset().mockResolvedValue(undefined)
  state.confirm.mockReset().mockResolvedValue(undefined)
  state.acquire.mockResolvedValue({
    shopId: 'shop',
    leaseId: 'lease',
    expectedVersion: 3,
  })
  state.release.mockResolvedValue(undefined)
  window.desktop = {
    appearance: { setTitleBarTheme() {} },
    managementLogin: bridge(),
  }
})

describe('page-owned shop login sync', () => {
  it('valid session still logs in; success invalidates list/detail metadata without closing browsing window', async () => {
    const { flow, wrapper } = setup()
    await flow.login(shop)
    await flushPromises()
    expect(state.success).toHaveBeenCalledWith('登录状态已更新')
    expect(state.invalidate).toHaveBeenCalledTimes(2)
    expect(window.desktop!.managementLogin!.close).not.toHaveBeenCalled()
    wrapper.unmount()
    expect(window.desktop!.managementLogin!.close).not.toHaveBeenCalled()
  })
  it('focuses an already open window before acquiring any new lease', async () => {
    window.desktop!.managementLogin!.focusShop = vi.fn().mockResolvedValue(true)
    const { flow, wrapper } = setup()
    await flow.login(shop)
    expect(state.acquire).not.toHaveBeenCalled()
    expect(window.desktop!.managementLogin!.open).not.toHaveBeenCalled()
    expect(state.success).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('duplicate clicks cannot start parallel save; pending cancel discards late receipt and releases lease', async () => {
    let finish!: (value: object) => void
    state.acquire.mockImplementation(
      () =>
        new Promise((resolve) => {
          finish = resolve
        }),
    )
    const { flow, wrapper } = setup()
    const opening = flow.login(shop)
    await flushPromises()
    await flow.login(shop)
    expect(state.acquire).toHaveBeenCalledTimes(1)
    await flow.cancel(shop.shopId)
    finish({ shopId: 'shop', leaseId: 'lease', expectedVersion: 3 })
    await opening
    expect(state.release).toHaveBeenCalledWith('shop', 'lease')
    expect(window.desktop!.managementLogin!.open).not.toHaveBeenCalled()
    expect(state.success).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('server failure preserves prior metadata and never claims historical valid as current success', async () => {
    window.desktop!.managementLogin!.refresh = vi
      .fn()
      .mockRejectedValue(new Error('platform failure'))
    const { flow, wrapper } = setup()
    await flow.login(shop)
    await flushPromises()
    expect(state.success).not.toHaveBeenCalled()
    expect(state.confirm).not.toHaveBeenCalled()
    expect(state.error).toHaveBeenCalledWith(
      expect.stringContaining('本次验证未完成'),
    )
    expect(state.release).toHaveBeenCalled()
    wrapper.unmount()
  })
  it('diagnostic baseline: failed identity detection triggers Renderer close and lease release without saving', async () => {
    window.desktop!.managementLogin!.getStatus = vi.fn().mockResolvedValue({
      attemptId: 'attempt',
      status: 'failed',
      message: 'synthetic document-context failure',
    })
    const { flow, wrapper } = setup()
    await flow.login(shop)
    await flushPromises()
    expect(window.desktop!.managementLogin!.close).toHaveBeenCalledWith(
      'attempt',
    )
    expect(state.release).toHaveBeenCalledWith('shop', 'lease')
    expect(window.desktop!.managementLogin!.refresh).not.toHaveBeenCalled()
    expect(state.confirm).not.toHaveBeenCalled()
    expect(state.success).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('preserves management authorization/platform capabilities and precise validation error semantics', async () => {
    state.auth.isSuperAccount = false
    const { flow, wrapper } = setup()
    await flow.login(shop)
    expect(state.acquire).not.toHaveBeenCalled()
    expect(supportsShopLogin('pdd')).toBe(true)
    expect(supportsShopLogin('taobao')).toBe(false)
    expect(
      validationFailureMessage(
        new ApiError({ message: 'business', code: 'PLATFORM_REQUEST_FAILED' }),
      ),
    ).toContain('验证未完成')
    expect(
      validationFailureMessage(
        new ApiError({ message: 'auth', code: 'AUTH_INVALID', status: 401 }),
      ),
    ).toContain('已失效')
    wrapper.unmount()
  })
  it('a read-refresh failure after a real save does not reclassify it as failed authentication', async () => {
    state.invalidate.mockRejectedValue(new Error('read unavailable'))
    const { flow, wrapper } = setup()
    await flow.login(shop)
    await flushPromises()
    expect(state.success).toHaveBeenCalledWith('登录状态已更新')
    expect(state.warning).toHaveBeenCalledWith('店铺信息刷新未完成，请刷新列表')
    expect(state.error).not.toHaveBeenCalled()
    expect(state.release).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('actor change during validation discards late success and cleans the old attempt', async () => {
    let finish!: (value: object) => void
    window.desktop!.managementLogin!.refresh = vi.fn().mockImplementation(
      () =>
        new Promise((resolve) => {
          finish = resolve
        }),
    )
    const { flow, wrapper } = setup()
    await flow.login(shop)
    await flushPromises()
    reactive(state.auth).activeTeamId = 'other-team'
    await flushPromises()
    finish({
      shopId: 'shop',
      status: 'valid',
      sessionVersion: 4,
      validatedAt: '2026-10-11T09:01:00Z',
    })
    await flushPromises()
    expect(state.success).not.toHaveBeenCalled()
    expect(state.confirm).not.toHaveBeenCalled()
    expect(flow.feedback.size).toBe(0)
    expect(window.desktop!.managementLogin!.close).toHaveBeenCalledWith(
      'attempt',
    )
    wrapper.unmount()
  })
  it('disposing while metadata refresh is pending suppresses stale success', async () => {
    const pending: Array<() => void> = []
    state.invalidate.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          pending.push(resolve)
        }),
    )
    const { flow, wrapper } = setup()
    await flow.login(shop)
    await flushPromises()
    wrapper.unmount()
    pending.forEach((finish) => finish())
    await flushPromises()
    expect(state.success).not.toHaveBeenCalled()
  })
})
