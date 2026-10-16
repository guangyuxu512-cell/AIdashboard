import { defineComponent, h, reactive } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  useShopLogin,
  supportsShopLogin,
  validationFailureMessage,
} from './useShopLogin'
import { ApiError } from '@/shared/api'
import type { ShopListItemViewModel } from '@/entities/shop'
import {
  LOGIN_FOCUS_TIMEOUT_MS,
  LOGIN_LEASE_TIMEOUT_MS,
  LOGIN_OPEN_TIMEOUT_MS,
} from './shop-login-diagnostics'

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
    correlationSupported: true as const,
    globalShopLoginSupported: true as const,
    focusShop: vi.fn().mockResolvedValue(false),
    open: vi.fn().mockResolvedValue({ attemptId: 'attempt' }),
    getStatus: vi.fn().mockResolvedValue({
      attemptId: 'attempt',
      status: 'identified',
      message: 'identified',
    }),
    refresh: vi.fn().mockResolvedValue({
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
  vi.spyOn(console, 'info').mockImplementation(() => undefined)
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
afterEach(() => {
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe('page-owned shop login sync', () => {
  it.each([true, undefined] as const)(
    'only a new bridge with explicit correlation support receives the extra IPC field (%s)',
    async (supported) => {
      window.desktop!.managementLogin = {
        ...bridge(),
        correlationSupported: supported,
      }
      const desktop = window.desktop!.managementLogin!
      desktop.getStatus = vi.fn().mockResolvedValue({
        attemptId: 'attempt',
        status: 'opened',
        message: '等待识别',
      })
      const { flow, wrapper } = setup()
      await flow.login(shop)
      await flushPromises()
      const focus = vi.mocked(desktop.focusShop!).mock.calls[0]![0]
      const opened = vi.mocked(desktop.open).mock.calls[0]![0]
      if (supported) {
        expect(focus.correlationId).toEqual(expect.any(String))
        expect(opened.correlationId).toBe(focus.correlationId)
        expect(opened.attemptId).toBe(focus.correlationId)
      } else {
        expect(Object.keys(focus).sort()).toEqual([
          'platform',
          'shopId',
          'teamId',
        ])
        expect(Object.keys(opened).sort()).toEqual([
          'attemptId',
          'platform',
          'recovery',
          'teamId',
        ])
      }
      vi.mocked(desktop.focusShop!).mockResolvedValue(true)
      await flow.login(shop)
      const again = vi.mocked(desktop.focusShop!).mock.calls[1]![0]
      if (supported) expect(again.correlationId).toBe(focus.correlationId)
      else expect(again).not.toHaveProperty('correlationId')
      expect(state.acquire).toHaveBeenCalledTimes(1)
      expect(desktop.open).toHaveBeenCalledTimes(1)
      expect(desktop.refresh).not.toHaveBeenCalled()
      wrapper.unmount()
    },
  )
  it('records missing bridge or required old-desktop upgrade before IPC, without directing a super account to choose a team', async () => {
    const { flow, wrapper } = setup()
    window.desktop = undefined
    await flow.login(shop)
    window.desktop = {
      appearance: { setTitleBarTheme() {} },
      managementLogin: { ...bridge(), globalShopLoginSupported: undefined },
    }
    reactive(state.auth).activeTeamId = ''
    await flushPromises()
    await flow.login(shop)
    const output = vi.mocked(console.info).mock.calls.flat().join('\n')
    expect(output).toContain('"bridgeAvailable":false')
    expect(output).toContain('"teamSelected":false')
    expect(output).toContain('NO_BRIDGE')
    expect(output).toContain('DESKTOP_UPGRADE_REQUIRED')
    expect(output).not.toContain('"person"')
    expect(output).not.toContain('"team"')
    expect(state.acquire).not.toHaveBeenCalled()
    expect(state.info).toHaveBeenCalledWith(
      '请更新桌面客户端以支持超级账号无团队登录',
    )
    wrapper.unmount()
  })
  it('super account without a team submits original shop/lease/CAS inputs without any fabricated team and retains the window after success', async () => {
    state.auth.activeTeamId = ''
    const { flow, wrapper } = setup()
    await flow.login(shop)
    await flushPromises()
    const desktop = window.desktop!.managementLogin!
    expect(vi.mocked(desktop.focusShop!).mock.calls[0]![0]).not.toHaveProperty(
      'teamId',
    )
    expect(vi.mocked(desktop.open).mock.calls[0]![0]).not.toHaveProperty(
      'teamId',
    )
    expect(vi.mocked(desktop.open).mock.calls[0]![0].recovery).toEqual({
      shopId: 'shop',
      leaseId: 'lease',
      expectedVersion: 3,
    })
    expect(state.success).toHaveBeenCalledWith('登录状态已更新')
    expect(state.auth.activeTeamId).toBe('')
    expect(desktop.close).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('a stale frontend super flag cannot bypass Backend denial on the unscoped metadata check', async () => {
    state.auth.activeTeamId = ''
    window.desktop!.managementLogin!.focusShop = vi
      .fn()
      .mockRejectedValue(new Error('SHOP_LOGIN_FORBIDDEN'))
    const { flow, wrapper } = setup()
    await flow.login(shop)
    expect(state.acquire).not.toHaveBeenCalled()
    expect(window.desktop!.managementLogin!.open).not.toHaveBeenCalled()
    expect(state.confirm).not.toHaveBeenCalled()
    expect(state.success).not.toHaveBeenCalled()
    expect(state.error).toHaveBeenCalledWith(expect.stringContaining('权限'))
    wrapper.unmount()
  })
  it('focus timeout clears opening feedback, ignores late receipt and permits a fresh retry without duplicate IPC', async () => {
    vi.useFakeTimers()
    let finish!: (result: boolean) => void
    const focus = vi.fn().mockImplementation(
      () =>
        new Promise<boolean>((resolve) => {
          finish = resolve
        }),
    )
    window.desktop!.managementLogin!.focusShop = focus
    const { flow, wrapper } = setup()
    const opening = flow.login(shop)
    await flushPromises()
    expect(flow.feedback.get('shop')).toMatchObject({
      busy: true,
      opening: true,
    })
    await flow.login(shop)
    expect(focus).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(LOGIN_FOCUS_TIMEOUT_MS)
    await opening
    expect(flow.feedback.get('shop')).toMatchObject({
      busy: false,
      opening: false,
    })
    expect(state.error).toHaveBeenCalledWith(expect.stringContaining('超时'))
    finish(false)
    await flushPromises()
    expect(state.acquire).not.toHaveBeenCalled()
    expect(window.desktop!.managementLogin!.open).not.toHaveBeenCalled()
    focus.mockResolvedValue(true)
    await flow.login(shop)
    expect(focus).toHaveBeenCalledTimes(2)
    expect(flow.feedback.has('shop')).toBe(false)
    wrapper.unmount()
  })
  it('lease timeout restores clickable state and releases only its late lease without opening or saving', async () => {
    vi.useFakeTimers()
    let finish!: (lease: object) => void
    state.acquire.mockImplementation(
      () =>
        new Promise((resolve) => {
          finish = resolve
        }),
    )
    const { flow, wrapper } = setup()
    const opening = flow.login(shop)
    await flushPromises()
    await vi.advanceTimersByTimeAsync(LOGIN_LEASE_TIMEOUT_MS)
    await opening
    expect(flow.feedback.get('shop')?.busy).toBe(false)
    finish({ shopId: 'shop', leaseId: 'late-lease', expectedVersion: 3 })
    await flushPromises()
    expect(state.release).toHaveBeenCalledWith('shop', 'late-lease')
    expect(window.desktop!.managementLogin!.open).not.toHaveBeenCalled()
    expect(state.confirm).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('open timeout closes the requested attempt and a late receipt, never saves or starts polling', async () => {
    vi.useFakeTimers()
    let finish!: (result: object) => void
    window.desktop!.managementLogin!.open = vi.fn().mockImplementation(
      () =>
        new Promise((resolve) => {
          finish = resolve
        }),
    )
    const { flow, wrapper } = setup()
    const opening = flow.login(shop)
    await flushPromises()
    const request = vi.mocked(window.desktop!.managementLogin!.open).mock
      .calls[0]![0]
    expect(request.attemptId).toBe(request.correlationId)
    await vi.advanceTimersByTimeAsync(LOGIN_OPEN_TIMEOUT_MS)
    await opening
    expect(window.desktop!.managementLogin!.close).toHaveBeenCalledWith(
      request.attemptId,
    )
    expect(flow.feedback.get('shop')?.busy).toBe(false)
    finish({ attemptId: 'late-attempt' })
    await flushPromises()
    expect(window.desktop!.managementLogin!.close).toHaveBeenCalledWith(
      'late-attempt',
    )
    expect(window.desktop!.managementLogin!.getStatus).not.toHaveBeenCalled()
    expect(window.desktop!.managementLogin!.refresh).not.toHaveBeenCalled()
    expect(state.success).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it.each(['team', 'permission'] as const)(
    'actor %s change during focus cannot allocate a lease or open from a late result',
    async (kind) => {
      let finish!: (result: boolean) => void
      window.desktop!.managementLogin!.focusShop = vi.fn().mockImplementation(
        () =>
          new Promise((resolve) => {
            finish = resolve
          }),
      )
      const { flow, wrapper } = setup()
      const opening = flow.login(shop)
      await flushPromises()
      if (kind === 'team') reactive(state.auth).activeTeamId = 'other-team'
      else reactive(state.auth).isSuperAccount = false
      await flushPromises()
      await opening
      finish(false)
      await flushPromises()
      expect(state.acquire).not.toHaveBeenCalled()
      expect(window.desktop!.managementLogin!.open).not.toHaveBeenCalled()
      expect(flow.feedback.size).toBe(0)
      expect(state.error).not.toHaveBeenCalled()
      wrapper.unmount()
    },
  )
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
  it('an active opened capture focuses once without new lease/open/save; polling cannot clear the focus guard', async () => {
    vi.useFakeTimers()
    const desktop = window.desktop!.managementLogin!
    desktop.getStatus = vi.fn().mockResolvedValue({
      attemptId: 'attempt',
      status: 'opened',
      message: '等待识别',
    })
    const { flow, wrapper } = setup()
    await flow.login(shop)
    await flushPromises()
    let finish!: (focused: boolean) => void
    vi.mocked(desktop.focusShop!).mockImplementation(
      () =>
        new Promise((resolve) => {
          finish = resolve
        }),
    )
    const focusing = flow.login(shop)
    await flushPromises()
    await vi.advanceTimersByTimeAsync(1500)
    expect(flow.feedback.get('shop')).toMatchObject({
      busy: true,
      opening: false,
      focusing: true,
    })
    await flow.login(shop)
    expect(desktop.focusShop).toHaveBeenCalledTimes(2)
    expect(state.acquire).toHaveBeenCalledTimes(1)
    expect(desktop.open).toHaveBeenCalledTimes(1)
    expect(desktop.refresh).not.toHaveBeenCalled()
    finish(true)
    await focusing
    expect(flow.feedback.get('shop')?.focusing).toBe(false)
    expect(desktop.close).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('native closed receipt clears busy during duplicate focus and lets a valid shop log in again without reviving the old flow', async () => {
    let finishStatus!: (result: ManagementLoginStatusResult) => void
    const desktop = window.desktop!.managementLogin!
    desktop.getStatus = vi.fn().mockImplementation(
      () =>
        new Promise((resolve) => {
          finishStatus = resolve
        }),
    )
    const { flow, wrapper } = setup()
    await flow.login(shop)
    await flushPromises()
    expect(flow.feedback.get('shop')?.busy).toBe(true)
    let finishFocus!: (focused: boolean) => void
    vi.mocked(desktop.focusShop!).mockImplementation(
      () =>
        new Promise((resolve) => {
          finishFocus = resolve
        }),
    )
    const focusing = flow.login(shop)
    await flushPromises()
    expect(flow.feedback.get('shop')?.focusing).toBe(true)
    finishStatus({
      attemptId: 'attempt',
      status: 'closed',
      message: '登录窗口已关闭',
      recovery: false,
    } as ManagementLoginStatusResult)
    await flushPromises()
    await focusing
    expect(flow.feedback.has('shop')).toBe(false)
    expect(desktop.close).toHaveBeenCalledExactlyOnceWith('attempt')
    expect(state.release).not.toHaveBeenCalled()
    finishFocus(true)
    await flushPromises()
    expect(flow.feedback.has('shop')).toBe(false)
    expect(desktop.refresh).not.toHaveBeenCalled()
    expect(state.success).not.toHaveBeenCalled()
    expect(state.confirm).not.toHaveBeenCalled()
    expect(shop.loginStatus).toBe('valid')
    vi.mocked(desktop.focusShop!).mockResolvedValue(false)
    desktop.getStatus = vi.fn().mockResolvedValue({
      attemptId: 'next-attempt',
      status: 'waiting',
      message: '等待登录',
    })
    await flow.login(shop)
    await flushPromises()
    expect(state.acquire).toHaveBeenCalledTimes(2)
    expect(desktop.open).toHaveBeenCalledTimes(2)
    expect(flow.feedback.get('shop')?.busy).toBe(true)
    wrapper.unmount()
  })
  it('a null bridge status clears busy with safe failure feedback and preserves the valid Session', async () => {
    const desktop = window.desktop!.managementLogin!
    desktop.getStatus = vi.fn().mockResolvedValue(null)
    const { flow, wrapper } = setup()
    await flow.login(shop)
    await flushPromises()
    expect(flow.feedback.get('shop')).toMatchObject({
      busy: false,
      opening: false,
    })
    expect(desktop.close).toHaveBeenCalledExactlyOnceWith('attempt')
    expect(state.release).toHaveBeenCalledExactlyOnceWith('shop', 'lease')
    expect(state.error).toHaveBeenCalledWith(
      expect.stringContaining('原登录状态保留'),
    )
    expect(state.confirm).not.toHaveBeenCalled()
    expect(state.success).not.toHaveBeenCalled()
    expect(shop.loginStatus).toBe('valid')
    wrapper.unmount()
  })
  it('active focus timeout restores the focus action without cancelling the ongoing capture or allocating another lease', async () => {
    vi.useFakeTimers()
    const desktop = window.desktop!.managementLogin!
    desktop.getStatus = vi.fn().mockResolvedValue({
      attemptId: 'attempt',
      status: 'opened',
      message: '等待识别',
    })
    const { flow, wrapper } = setup()
    await flow.login(shop)
    await flushPromises()
    vi.mocked(desktop.focusShop!).mockImplementation(
      () => new Promise(() => {}),
    )
    const focusing = flow.login(shop)
    await vi.advanceTimersByTimeAsync(LOGIN_FOCUS_TIMEOUT_MS)
    await focusing
    expect(flow.feedback.get('shop')).toMatchObject({
      busy: true,
      opening: false,
      focusing: false,
    })
    expect(desktop.close).not.toHaveBeenCalled()
    expect(state.release).not.toHaveBeenCalled()
    vi.mocked(desktop.focusShop!).mockResolvedValue(true)
    await flow.login(shop)
    expect(desktop.focusShop).toHaveBeenCalledTimes(3)
    expect(state.acquire).toHaveBeenCalledTimes(1)
    expect(desktop.open).toHaveBeenCalledTimes(1)
    expect(desktop.refresh).not.toHaveBeenCalled()
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
  it('a supported refresh rejection retains the window and waits for explicit continuation without saving', async () => {
    const desktop = window.desktop!.managementLogin!
    Object.assign(desktop, { refreshRecoverySupported: true })
    desktop.refresh = vi.fn().mockRejectedValue(new Error('fixed rejection'))
    desktop.getStatus = vi
      .fn()
      .mockResolvedValueOnce({
        attemptId: 'attempt',
        status: 'identified',
        message: 'identified',
      })
      .mockResolvedValue({
        attemptId: 'attempt',
        status: 'failed',
        recovery: false,
        message: '本次验证未完成，请在原窗口完成登录后点击继续登录',
        refreshFailure: { canContinue: true },
      })
    const { flow, wrapper } = setup()
    await flow.login(shop)
    await flushPromises()
    expect(desktop.close).not.toHaveBeenCalled()
    expect(state.confirm).not.toHaveBeenCalled()
    expect(state.success).not.toHaveBeenCalled()
    expect(flow.feedback.get('shop')).toMatchObject({
      busy: true,
      retryReady: true,
    })
    expect(state.acquire).toHaveBeenCalledTimes(1)
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
  it('explicit continuation uses the same attempt and a freshly acquired version without duplicate open or save', async () => {
    const desktop = window.desktop!.managementLogin!
    Object.assign(desktop, { refreshRecoverySupported: true })
    desktop.getStatus = vi
      .fn()
      .mockResolvedValueOnce({
        attemptId: 'attempt',
        status: 'identified',
        message: 'identified',
      })
      .mockResolvedValue({
        attemptId: 'attempt',
        status: 'failed',
        recovery: false,
        message: '请点击继续登录',
        refreshFailure: { canContinue: true },
      })
    desktop.refresh = vi
      .fn()
      .mockRejectedValueOnce(new Error('fixed rejection'))
      .mockResolvedValue({
        shopId: 'shop',
        status: 'valid',
        sessionVersion: 6,
        validatedAt: '2026-10-16T01:00:00Z',
      })
    const { flow, wrapper } = setup()
    await flow.login(shop)
    await flushPromises()
    state.acquire.mockResolvedValue({
      shopId: 'shop',
      leaseId: 'fresh-lease',
      expectedVersion: 5,
    })
    desktop.getStatus = vi.fn().mockResolvedValue({
      attemptId: 'attempt',
      status: 'identified',
      message: 'identified',
    })
    await Promise.all([flow.login(shop), flow.login(shop)])
    await flushPromises()
    expect(state.acquire).toHaveBeenCalledTimes(2)
    expect(desktop.open).toHaveBeenCalledTimes(2)
    expect(vi.mocked(desktop.open).mock.calls[1]![0]).toMatchObject({
      attemptId: 'attempt',
      recovery: { shopId: 'shop', leaseId: 'fresh-lease', expectedVersion: 5 },
    })
    expect(desktop.focusShop).toHaveBeenCalledTimes(1)
    expect(desktop.refresh).toHaveBeenCalledTimes(2)
    expect(state.confirm).toHaveBeenCalledExactlyOnceWith(
      'shop',
      6,
      '2026-10-16T01:00:00Z',
    )
    expect(state.success).toHaveBeenCalledExactlyOnceWith('登录状态已更新')
    expect(desktop.close).not.toHaveBeenCalled()
    expect(flow.feedback.size).toBe(0)
    wrapper.unmount()
  })
  it('retained failure status polling never resubmits and a natural close clears feedback without duplicate lease release', async () => {
    vi.useFakeTimers()
    const desktop = window.desktop!.managementLogin!
    Object.assign(desktop, { refreshRecoverySupported: true })
    desktop.refresh = vi.fn().mockRejectedValue(new Error('fixed rejection'))
    const failed = {
      attemptId: 'attempt',
      status: 'failed',
      recovery: false,
      message: '请点击继续登录',
      refreshFailure: { canContinue: true },
    }
    const getStatus = vi
      .fn()
      .mockResolvedValueOnce({
        attemptId: 'attempt',
        status: 'identified',
        message: 'identified',
      })
      .mockResolvedValue(failed)
    desktop.getStatus = getStatus
    const { flow, wrapper } = setup()
    await flow.login(shop)
    await flushPromises()
    await vi.advanceTimersByTimeAsync(4500)
    expect(desktop.refresh).toHaveBeenCalledTimes(1)
    expect(state.acquire).toHaveBeenCalledTimes(1)
    expect(state.error).toHaveBeenCalledTimes(1)
    expect(desktop.close).not.toHaveBeenCalled()
    getStatus.mockResolvedValue({
      attemptId: 'attempt',
      status: 'closed',
      recovery: false,
      message: 'closed',
    })
    await vi.advanceTimersByTimeAsync(3000)
    expect(flow.feedback.size).toBe(0)
    expect(desktop.close).toHaveBeenCalledExactlyOnceWith('attempt')
    expect(state.release).not.toHaveBeenCalled()
    expect(state.success).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  it('cancel during continuation releases only the late fresh lease and never revives or opens another window', async () => {
    const desktop = window.desktop!.managementLogin!
    Object.assign(desktop, { refreshRecoverySupported: true })
    desktop.refresh = vi.fn().mockRejectedValue(new Error('fixed rejection'))
    desktop.getStatus = vi
      .fn()
      .mockResolvedValueOnce({
        attemptId: 'attempt',
        status: 'identified',
        message: 'identified',
      })
      .mockResolvedValue({
        attemptId: 'attempt',
        status: 'failed',
        recovery: false,
        message: '请点击继续登录',
        refreshFailure: { canContinue: true },
      })
    const { flow, wrapper } = setup()
    await flow.login(shop)
    await flushPromises()
    let finish!: (lease: object) => void
    state.acquire.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve
        }),
    )
    const continuing = flow.login(shop)
    await flushPromises()
    await flow.cancel('shop')
    finish({ shopId: 'shop', leaseId: 'late-lease', expectedVersion: 3 })
    await continuing
    await flushPromises()
    expect(state.release).toHaveBeenCalledExactlyOnceWith('shop', 'late-lease')
    expect(desktop.open).toHaveBeenCalledTimes(1)
    expect(desktop.refresh).toHaveBeenCalledTimes(1)
    expect(state.success).not.toHaveBeenCalled()
    expect(flow.feedback.size).toBe(0)
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
