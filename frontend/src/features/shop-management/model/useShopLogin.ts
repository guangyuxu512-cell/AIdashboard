import {
  computed,
  onScopeDispose,
  reactive,
  watch,
  type InjectionKey,
} from 'vue'
import { useQueryClient } from '@tanstack/vue-query'
import { useMessage } from 'naive-ui'
import dayjs from 'dayjs'
import { useAuthStore } from '@/stores/auth'
import { getPlatformDefinition } from '@/entities/platform'
import { shopQueryKeys, type ShopListItemViewModel } from '@/entities/shop'
import {
  shopSessionDataSource,
  shopSessionQueryKeys,
} from '@/entities/shop-session'
import { ApiError } from '@/shared/api'
import { startManagementLoginPolling } from './management-login-poller'
import {
  LOGIN_FOCUS_TIMEOUT_MS,
  LOGIN_LEASE_TIMEOUT_MS,
  LOGIN_OPEN_TIMEOUT_MS,
  reportLoginStage,
  waitForLoginOpening,
  openingErrorCode,
  openingFailureMessage,
  type LoginOpeningPhase,
} from './shop-login-diagnostics'

export function supportsShopLogin(platform: string): boolean {
  const capabilities = getPlatformDefinition(platform)?.capabilities
  return (
    capabilities?.authentication === 'available' &&
    capabilities.sessionCapture === 'available'
  )
}

export function validationFailureMessage(error: unknown): string {
  return error instanceof ApiError && error.code === 'AUTH_INVALID'
    ? '登录状态已失效，请点击登录重新授权'
    : '本次验证未完成，请稍后重试或点击登录'
}

interface LoginFlow {
  shopId: string
  scopeVersion: number
  actorId: string | undefined
  teamId?: string
  attemptId?: string
  leaseId?: string
  stop?: () => void
  correlationId: string
  abort: AbortController
  leaseReleaseStarted?: boolean
  windowOpened?: boolean
  focusing?: boolean
  retryReady?: boolean
  captureGeneration?: number
}
export interface ShopLoginFeedback {
  busy: boolean
  opening: boolean
  focusing?: boolean
  retryReady?: boolean
  retryBlocked?: boolean
  success?: {
    sessionVersion: number
    validatedAt: string
    readRefreshFailed: boolean
  }
  error: string | null
  status: string | null
}
export const shopLoginKey: InjectionKey<ReturnType<typeof useShopLogin>> =
  Symbol('shop-login')

// One page-owned flow is shared by list/detail. Completed browsing windows are
// owned only by Main; no renderer lease or captured payload survives success.
export function useShopLogin() {
  const auth = useAuthStore()
  const queries = useQueryClient()
  const message = useMessage()
  const active = new Map<string, LoginFlow>()
  let scopeVersion = 0
  const feedback = reactive(new Map<string, ShopLoginFeedback>())
  const canLogin = computed(() => auth.isSuperAccount)
  function current(flow: LoginFlow) {
    return (
      flow.scopeVersion === scopeVersion &&
      auth.currentUser?.userId === flow.actorId &&
      (auth.activeTeamId || undefined) === flow.teamId &&
      auth.isSuperAccount &&
      active.get(flow.shopId) === flow
    )
  }
  async function refresh(shopId: string) {
    await Promise.all([
      queries.invalidateQueries(
        { queryKey: shopSessionQueryKeys.shop(shopId) },
        { throwOnError: true },
      ),
      queries.invalidateQueries(
        { queryKey: shopQueryKeys.all },
        { throwOnError: true },
      ),
    ])
  }
  async function cancel(shopId: string) {
    const flow = active.get(shopId)
    if (!flow) return
    active.delete(shopId)
    flow.abort.abort()
    flow.stop?.()
    feedback.delete(shopId)
    if (flow.attemptId) {
      const closing = window.desktop?.managementLogin?.close(flow.attemptId)
      if (closing) void cleanup(flow, closing)
    }
    if (flow.leaseId) releaseLease(flow)
  }
  async function cleanup(flow: LoginFlow, pending: Promise<unknown>) {
    const started = Date.now()
    reportLoginStage(flow.correlationId, 'cleanup', 'start')
    try {
      await waitForLoginOpening(pending, 5_000)
      reportLoginStage(flow.correlationId, 'cleanup', 'finish', {
        elapsedMs: Date.now() - started,
      })
    } catch (error) {
      reportLoginStage(flow.correlationId, 'cleanup', 'error', {
        errorCode: openingErrorCode(error),
        elapsedMs: Date.now() - started,
      })
    }
  }
  function releaseLease(flow: LoginFlow) {
    if (!flow.leaseId || flow.leaseReleaseStarted) return
    flow.leaseReleaseStarted = true
    void cleanup(
      flow,
      shopSessionDataSource.releaseRefreshLease(flow.shopId, flow.leaseId),
    )
  }
  async function openingStep<T>(
    flow: LoginFlow,
    phase: LoginOpeningPhase,
    pending: Promise<T>,
    timeoutMs: number,
  ) {
    const started = Date.now()
    reportLoginStage(flow.correlationId, phase, 'start')
    try {
      const result = await waitForLoginOpening(
        pending,
        timeoutMs,
        flow.abort.signal,
      )
      reportLoginStage(flow.correlationId, phase, 'finish', {
        elapsedMs: Date.now() - started,
      })
      return result
    } catch (error) {
      reportLoginStage(flow.correlationId, phase, 'error', {
        errorCode: openingErrorCode(error),
        httpStatus: error instanceof ApiError ? error.status : null,
        elapsedMs: Date.now() - started,
      })
      throw error
    }
  }
  async function fail(flow: LoginFlow, text: string) {
    if (!current(flow)) return
    await cancel(flow.shopId)
    if (flow.scopeVersion !== scopeVersion || active.has(flow.shopId)) return
    feedback.set(flow.shopId, {
      busy: false,
      opening: false,
      error: text,
      status: null,
    })
    message.error(text)
  }
  function retainForContinue(
    flow: LoginFlow,
    status: ManagementLoginStatusResult,
  ) {
    if (
      !current(flow) ||
      window.desktop?.managementLogin?.refreshRecoverySupported !== true ||
      status.status !== 'failed' ||
      !status.refreshFailure
    )
      return false
    if (status.recovery === false) flow.leaseReleaseStarted = true
    else releaseLease(flow)
    flow.retryReady = status.refreshFailure.canContinue
    if (
      feedback.get(flow.shopId)?.error === status.message &&
      feedback.get(flow.shopId)?.retryReady === flow.retryReady
    )
      return true
    feedback.set(flow.shopId, {
      busy: true,
      opening: false,
      retryReady: flow.retryReady,
      retryBlocked: !flow.retryReady,
      error: status.message,
      status: null,
    })
    message.error(status.message)
    return true
  }
  function observeRetainedWindow(
    flow: LoginFlow,
    getStatus: (attemptId: string) => Promise<ManagementLoginStatusResult>,
  ) {
    if (!flow.attemptId) return
    const generation = flow.captureGeneration
    const observing = () =>
      current(flow) && flow.captureGeneration === generation
    flow.stop?.()
    flow.stop = startManagementLoginPolling({
      attemptId: flow.attemptId,
      getStatus,
      async onStatus(status) {
        if (!observing()) return
        if (status.status === 'closed' || status.status === 'completed') {
          // This receipt describes Main's old lease, not a freshly acquired
          // renderer lease. cancel must still release any new lease it owns.
          await cancel(flow.shopId)
          return
        }
        // Read only: never capture, refresh, overwrite the lease error or toast.
        return true
      },
      onError() {
        if (observing())
          void fail(flow, '登录窗口状态读取未完成，请重新打开登录')
      },
    })
  }
  async function login(shop: ShopListItemViewModel) {
    const existing = active.get(shop.shopId)
    const correlationId = existing?.correlationId ?? crypto.randomUUID()
    const bridge = window.desktop?.managementLogin
    const teamId = auth.activeTeamId || undefined
    const eligiblePlatform = supportsShopLogin(shop.platform)
    reportLoginStage(correlationId, 'entry', 'start', {
      bridgeAvailable: Boolean(bridge?.focusShop),
      superAccount: canLogin.value,
      teamSelected: Boolean(teamId),
      platformSupported: eligiblePlatform,
    })
    if (!canLogin.value || !eligiblePlatform) {
      reportLoginStage(correlationId, 'entry', 'blocked', {
        errorCode: !canLogin.value ? 'NOT_ALLOWED' : 'UNSUPPORTED_PLATFORM',
      })
      message.info(
        !canLogin.value ? '当前账号无店铺登录权限' : '该平台暂不支持店铺登录',
      )
      return
    }
    if (!bridge?.focusShop) {
      message.info('请安装支持店铺登录同步的新桌面版本')
      reportLoginStage(correlationId, 'entry', 'blocked', {
        errorCode: 'NO_BRIDGE',
      })
      return
    }
    if (!teamId && bridge.globalShopLoginSupported !== true) {
      message.info('请更新桌面客户端以支持超级账号无团队登录')
      reportLoginStage(correlationId, 'entry', 'blocked', {
        errorCode: 'DESKTOP_UPGRADE_REQUIRED',
      })
      return
    }
    if (shop.platform !== 'douyin' && shop.platform !== 'pdd') return
    // Published 1.0.4 accepts only the original IPC fields. The new constant
    // is diagnostic-specific, not a general version/capability framework.
    const correlation =
      bridge.correlationSupported === true ? { correlationId } : {}
    const teamContext = teamId ? { teamId } : {}
    const retrying = Boolean(existing?.retryReady)
    if (existing && !retrying) {
      if (!current(existing) || !existing.windowOpened || existing.focusing) {
        reportLoginStage(correlationId, 'entry', 'duplicate')
        return
      }
      existing.focusing = true
      const existingFeedback = feedback.get(shop.shopId)!
      feedback.set(shop.shopId, {
        ...existingFeedback,
        focusing: true,
        error:
          existingFeedback.retryReady || existingFeedback.retryBlocked
            ? existingFeedback.error
            : null,
      })
      try {
        const focused = await openingStep(
          existing,
          'focus',
          bridge.focusShop({
            platform: shop.platform,
            shopId: shop.shopId,
            ...teamContext,
            ...correlation,
          }),
          LOGIN_FOCUS_TIMEOUT_MS,
        )
        if (current(existing) && !focused)
          message.info('未找到登录窗口，请取消后重新登录')
      } catch (error) {
        if (current(existing)) {
          const text = openingFailureMessage(error)
          feedback.set(shop.shopId, {
            ...feedback.get(shop.shopId)!,
            error: text,
          })
          message.error(text)
        }
      } finally {
        existing.focusing = false
        if (current(existing))
          feedback.set(shop.shopId, {
            ...feedback.get(shop.shopId)!,
            focusing: false,
          })
      }
      return
    }
    if (existing && (!current(existing) || existing.focusing)) return
    const flow: LoginFlow = existing ?? {
      shopId: shop.shopId,
      scopeVersion,
      actorId: auth.currentUser?.userId,
      teamId,
      correlationId,
      attemptId: correlationId,
      abort: new AbortController(),
    }
    flow.retryReady = false
    flow.focusing = retrying
    flow.stop?.()
    const generation = (flow.captureGeneration ?? 0) + 1
    flow.captureGeneration = generation
    const captureCurrent = () =>
      current(flow) && flow.captureGeneration === generation
    active.set(shop.shopId, flow)
    feedback.set(shop.shopId, {
      busy: true,
      opening: true,
      error: null,
      status: retrying ? '正在继续原窗口登录验证' : '正在打开店铺登录窗口',
    })
    let acceptingLease = true
    let leaseStepCompleted = false
    try {
      if (retrying) observeRetainedWindow(flow, bridge.getStatus)
      else {
        const focused = await openingStep(
          flow,
          'focus',
          bridge.focusShop({
            platform: shop.platform,
            shopId: shop.shopId,
            ...teamContext,
            ...correlation,
          }),
          LOGIN_FOCUS_TIMEOUT_MS,
        )
        if (!current(flow)) return
        if (focused) {
          active.delete(shop.shopId)
          feedback.delete(shop.shopId)
          return
        }
      }
      const pendingLease = shopSessionDataSource
        .acquireRefreshLease(shop.shopId)
        .then((lease) => {
          if (!acceptingLease || !captureCurrent()) {
            void cleanup(
              flow,
              shopSessionDataSource.releaseRefreshLease(
                shop.shopId,
                lease.leaseId,
              ),
            )
          } else {
            flow.leaseId = lease.leaseId
            flow.leaseReleaseStarted = false
          }
          return lease
        })
      const lease = await openingStep(
        flow,
        'lease',
        pendingLease,
        LOGIN_LEASE_TIMEOUT_MS,
      )
      leaseStepCompleted = true
      if (!current(flow)) {
        releaseLease(flow)
        return
      }
      // The old window stays observable throughout lease acquisition, including
      // rejection/timeout. Stop only when the fresh lease can rearm Main.
      flow.stop?.()
      const opened = await openingStep(
        flow,
        'open',
        bridge
          .open({
            platform: shop.platform,
            ...teamContext,
            attemptId: flow.attemptId,
            ...correlation,
            recovery: {
              shopId: shop.shopId,
              leaseId: lease.leaseId,
              expectedVersion: lease.expectedVersion,
            },
          })
          .then((opened) => {
            if (!current(flow))
              void cleanup(flow, bridge.close(opened.attemptId))
            return opened
          }),
        LOGIN_OPEN_TIMEOUT_MS,
      )
      flow.attemptId = opened.attemptId
      if (!current(flow)) {
        void cleanup(flow, bridge.close(opened.attemptId))
        return
      }
      flow.windowOpened = true
      feedback.set(shop.shopId, {
        busy: true,
        opening: false,
        error: null,
        status: '登录窗口已打开，等待识别店铺',
      })
      flow.stop = startManagementLoginPolling({
        attemptId: opened.attemptId,
        getStatus: bridge.getStatus,
        async onStatus(status) {
          if (!captureCurrent()) return
          if (status.status === 'failed' && retainForContinue(flow, status))
            return true
          feedback.set(shop.shopId, {
            busy: true,
            opening: false,
            focusing: flow.focusing ?? false,
            error: null,
            status: status.message,
          })
          if (status.status === 'closed') {
            // Main clears recovery before its once-only release attempt.
            // Keep the existing fallback for older/failed bridge replies.
            if (status.recovery === false) flow.leaseReleaseStarted = true
            await cancel(shop.shopId)
            return
          }
          if (status.status === 'failed') {
            await fail(flow, '本次验证未完成，请重新打开登录窗口')
            return
          }
          if (status.status !== 'identified') return
          let result
          try {
            result = await bridge.refresh(status.attemptId)
          } catch (error) {
            if (bridge.refreshRecoverySupported === true && captureCurrent()) {
              const rejected = await waitForLoginOpening(
                bridge.getStatus(status.attemptId),
                LOGIN_FOCUS_TIMEOUT_MS,
                flow.abort.signal,
              )
              if (captureCurrent() && retainForContinue(flow, rejected))
                return true
            }
            throw error
          }
          if (!captureCurrent()) return
          if (
            result.shopId !== shop.shopId ||
            result.status !== 'valid' ||
            result.sessionVersion !== lease.expectedVersion + 1 ||
            typeof result.validatedAt !== 'string' ||
            !Number.isFinite(Date.parse(result.validatedAt))
          )
            throw new Error('未取得本次有效验证结果')
          await shopSessionDataSource.confirmRecovery(
            result.shopId,
            result.sessionVersion,
            result.validatedAt,
          )
          if (!captureCurrent()) return
          let readRefreshFailed = false
          try {
            await refresh(shop.shopId)
          } catch {
            readRefreshFailed = true
          }
          if (!captureCurrent()) return
          active.delete(shop.shopId)
          feedback.set(shop.shopId, {
            busy: false,
            opening: false,
            error: null,
            status: `本次登录已更新（v${result.sessionVersion} · ${dayjs(result.validatedAt).format('YYYY-MM-DD HH:mm')}）${readRefreshFailed ? '；店铺信息刷新未完成，请刷新列表' : ''}`,
            success: {
              sessionVersion: result.sessionVersion,
              validatedAt: result.validatedAt,
              readRefreshFailed,
            },
          })
          message.success('登录状态已更新')
          if (readRefreshFailed)
            message.warning('店铺信息刷新未完成，请刷新列表')
          if (result.profileMappingWarning)
            message.warning(result.profileMappingWarning)
        },
        onError() {
          if (captureCurrent())
            void fail(flow, '本次验证未完成，原登录状态保留；请稍后重试')
        },
      })
    } catch (error) {
      if (retrying && !leaseStepCompleted && current(flow)) {
        const code = openingErrorCode(error)
        flow.retryReady = code !== 'AUTH_REQUIRED' && code !== 'FORBIDDEN'
        feedback.set(shop.shopId, {
          busy: true,
          opening: false,
          retryReady: flow.retryReady,
          retryBlocked: !flow.retryReady,
          error: openingFailureMessage(error),
          status: null,
        })
        message.error(openingFailureMessage(error))
        return
      }
      await fail(flow, openingFailureMessage(error))
    } finally {
      acceptingLease = false
      flow.focusing = false
    }
  }
  watch(
    () =>
      `${auth.currentUser?.userId}:${auth.activeTeamId || ''}:${auth.isSuperAccount}`,
    () => {
      scopeVersion++
      for (const shopId of active.keys()) void cancel(shopId)
      feedback.clear()
    },
  )
  onScopeDispose(() => {
    scopeVersion++
    for (const shopId of active.keys()) void cancel(shopId)
    feedback.clear()
  })
  return { canLogin, feedback, login, cancel, refresh }
}
