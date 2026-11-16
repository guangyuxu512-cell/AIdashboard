import { effectScope, type EffectScope } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  MOBILE_PULL_REFRESH_ERROR_DURATION_MS,
  MOBILE_PULL_REFRESH_HAPTIC_DURATION_MS,
  MOBILE_PULL_REFRESH_MINIMUM_DURATION_MS,
  MOBILE_PULL_REFRESH_REBOUND_DURATION_MS,
  MOBILE_PULL_REFRESH_SUCCESS_DURATION_MS,
  useMobilePullRefresh,
} from '@/shared/ui/mobile-pull-refresh'

function createDeferred<T>() {
  let resolve: (value: T) => void = () => undefined
  const promise = new Promise<T>((nextResolve) => {
    resolve = nextResolve
  })
  return { promise, resolve }
}

function createController(refresh: () => Promise<boolean>) {
  const scope = effectScope()
  const controller = scope.run(() => useMobilePullRefresh(refresh))
  if (!controller) throw new Error('未能创建下拉刷新控制器')
  return { controller, scope }
}

function installReducedMotion(matches: boolean): void {
  const mediaQuery = {
    matches,
    media: '(prefers-reduced-motion: reduce)',
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
  } as unknown as MediaQueryList
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn(() => mediaQuery),
  })
}

describe('useMobilePullRefresh', () => {
  let scope: EffectScope | undefined

  afterEach(() => {
    scope?.stop()
    scope = undefined
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('starts the real request immediately, keeps a short loading state, and ignores repeat pulls', async () => {
    vi.useFakeTimers()
    const deferred = createDeferred<boolean>()
    const refresh = vi.fn(() => deferred.promise)
    const harness = createController(refresh)
    scope = harness.scope

    const firstRefresh = harness.controller.runRefresh()
    await Promise.resolve()
    void harness.controller.runRefresh()

    expect(refresh).toHaveBeenCalledTimes(1)
    expect(harness.controller.refreshing.value).toBe(true)

    deferred.resolve(true)
    await Promise.resolve()
    await vi.advanceTimersByTimeAsync(
      MOBILE_PULL_REFRESH_MINIMUM_DURATION_MS - 1,
    )
    expect(harness.controller.refreshing.value).toBe(true)

    await vi.advanceTimersByTimeAsync(1)
    await firstRefresh
    expect(harness.controller.refreshing.value).toBe(false)
    expect(harness.controller.feedback.value).toBe('success')
    expect(harness.controller.feedbackDuration.value).toBe(
      MOBILE_PULL_REFRESH_SUCCESS_DURATION_MS,
    )
    expect(harness.controller.reboundDuration.value).toBe(
      MOBILE_PULL_REFRESH_REBOUND_DURATION_MS,
    )
  })

  it('keeps existing content eligible for an error feedback and reports failure consistently', async () => {
    vi.useFakeTimers()
    const harness = createController(async () => false)
    scope = harness.scope

    const refresh = harness.controller.runRefresh()
    await vi.advanceTimersByTimeAsync(MOBILE_PULL_REFRESH_MINIMUM_DURATION_MS)
    await refresh

    expect(harness.controller.refreshing.value).toBe(false)
    expect(harness.controller.feedback.value).toBe('error')
    expect(harness.controller.feedbackDuration.value).toBe(
      MOBILE_PULL_REFRESH_ERROR_DURATION_MS,
    )
  })

  it('vibrates once at the release threshold for each supported gesture', () => {
    const vibrate = vi.fn(() => true)
    Object.defineProperty(navigator, 'vibrate', {
      configurable: true,
      value: vibrate,
    })
    const harness = createController(async () => true)
    scope = harness.scope

    harness.controller.handleChange({ status: 'pulling' })
    harness.controller.handleChange({ status: 'loosing' })
    harness.controller.handleChange({ status: 'pulling' })
    harness.controller.handleChange({ status: 'loosing' })

    expect(vibrate).toHaveBeenCalledTimes(1)
    expect(vibrate).toHaveBeenCalledWith(MOBILE_PULL_REFRESH_HAPTIC_DURATION_MS)

    harness.controller.handleChange({ status: 'normal' })
    harness.controller.handleChange({ status: 'pulling' })
    harness.controller.handleChange({ status: 'loosing' })
    expect(vibrate).toHaveBeenCalledTimes(2)
  })

  it('removes motion and haptic feedback when reduced motion is requested', () => {
    installReducedMotion(true)
    const vibrate = vi.fn(() => true)
    Object.defineProperty(navigator, 'vibrate', {
      configurable: true,
      value: vibrate,
    })
    const harness = createController(async () => true)
    scope = harness.scope

    harness.controller.handleChange({ status: 'pulling' })
    harness.controller.handleChange({ status: 'loosing' })

    expect(harness.controller.reboundDuration.value).toBe(0)
    expect(vibrate).not.toHaveBeenCalled()
  })

  it('ignores late refresh results after its scope is disposed', async () => {
    const deferred = createDeferred<boolean>()
    const harness = createController(() => deferred.promise)
    scope = harness.scope

    const refresh = harness.controller.runRefresh()
    harness.scope.stop()
    scope = undefined
    deferred.resolve(true)
    await refresh

    expect(harness.controller.refreshing.value).toBe(false)
    expect(harness.controller.feedback.value).toBeNull()
  })
})
