import { computed, onScopeDispose, ref } from 'vue'

export const MOBILE_PULL_REFRESH_MINIMUM_DURATION_MS = 350
export const MOBILE_PULL_REFRESH_SUCCESS_DURATION_MS = 500
export const MOBILE_PULL_REFRESH_ERROR_DURATION_MS = 1_200
export const MOBILE_PULL_REFRESH_REBOUND_DURATION_MS = 220
export const MOBILE_PULL_REFRESH_HAPTIC_DURATION_MS = 10

export type MobilePullRefreshFeedback = 'success' | 'error' | null
export type MobilePullRefreshGestureStatus =
  'normal' | 'pulling' | 'loosing' | 'loading' | 'success'

interface MobilePullRefreshChangeEvent {
  status: MobilePullRefreshGestureStatus
}

interface PendingTimer {
  timer: number
  resolve: () => void
}

function createReducedMotionPreference() {
  const prefersReducedMotion = ref(false)
  let mediaQuery: MediaQueryList | null = null

  if (typeof window !== 'undefined' && window.matchMedia) {
    mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
    prefersReducedMotion.value = mediaQuery.matches
    const updatePreference = (event: MediaQueryListEvent) => {
      prefersReducedMotion.value = event.matches
    }

    if (typeof mediaQuery.addEventListener === 'function') {
      mediaQuery.addEventListener('change', updatePreference)
      onScopeDispose(() =>
        mediaQuery?.removeEventListener('change', updatePreference),
      )
    } else {
      mediaQuery.addListener(updatePreference)
      onScopeDispose(() => mediaQuery?.removeListener(updatePreference))
    }
  }

  return prefersReducedMotion
}

function triggerThresholdHaptic(): void {
  if (
    typeof navigator === 'undefined' ||
    typeof navigator.vibrate !== 'function'
  ) {
    return
  }

  try {
    navigator.vibrate(MOBILE_PULL_REFRESH_HAPTIC_DURATION_MS)
  } catch {
    // iPhone Safari/PWA generally has no standard Vibration API; visual feedback remains.
  }
}

export function useMobilePullRefresh(refresh: () => Promise<boolean>) {
  const refreshing = ref(false)
  const feedback = ref<MobilePullRefreshFeedback>(null)
  const prefersReducedMotion = createReducedMotionPreference()
  const feedbackDuration = computed(() => {
    if (prefersReducedMotion.value) return 0
    return feedback.value === 'error'
      ? MOBILE_PULL_REFRESH_ERROR_DURATION_MS
      : MOBILE_PULL_REFRESH_SUCCESS_DURATION_MS
  })
  const reboundDuration = computed(() =>
    prefersReducedMotion.value ? 0 : MOBILE_PULL_REFRESH_REBOUND_DURATION_MS,
  )
  const pendingTimers = new Set<PendingTimer>()
  let disposed = false
  let refreshRun = 0
  let gestureActive = false
  let thresholdHapticTriggered = false

  function wait(milliseconds: number): Promise<void> {
    if (milliseconds <= 0) return Promise.resolve()

    return new Promise((resolve) => {
      const pending: PendingTimer = {
        timer: window.setTimeout(() => {
          pendingTimers.delete(pending)
          resolve()
        }, milliseconds),
        resolve,
      }
      pendingTimers.add(pending)
    })
  }

  function handleChange(event: MobilePullRefreshChangeEvent): void {
    if (event.status === 'pulling' && !gestureActive) {
      gestureActive = true
      thresholdHapticTriggered = false
    }

    if (
      event.status === 'loosing' &&
      gestureActive &&
      !thresholdHapticTriggered &&
      !prefersReducedMotion.value
    ) {
      thresholdHapticTriggered = true
      triggerThresholdHaptic()
    }

    if (event.status === 'normal') {
      gestureActive = false
      thresholdHapticTriggered = false
    }
  }

  async function runRefresh(): Promise<void> {
    if (disposed || refreshing.value) return

    const currentRun = ++refreshRun
    const startedAt = Date.now()
    refreshing.value = true
    feedback.value = null

    let succeeded = false
    try {
      succeeded = await refresh()
    } catch {
      succeeded = false
    }

    if (disposed || currentRun !== refreshRun) return

    const elapsed = Date.now() - startedAt
    await wait(Math.max(0, MOBILE_PULL_REFRESH_MINIMUM_DURATION_MS - elapsed))

    if (disposed || currentRun !== refreshRun) return

    feedback.value = succeeded ? 'success' : 'error'
    refreshing.value = false
  }

  onScopeDispose(() => {
    disposed = true
    refreshRun += 1
    refreshing.value = false
    feedback.value = null
    for (const pending of pendingTimers) {
      window.clearTimeout(pending.timer)
      pending.resolve()
    }
    pendingTimers.clear()
  })

  return {
    feedback,
    feedbackDuration,
    handleChange,
    reboundDuration,
    refreshing,
    runRefresh,
  }
}
