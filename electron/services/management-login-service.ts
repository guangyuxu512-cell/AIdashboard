import {
  app,
  BrowserWindow,
  session,
  type Session,
  type BrowserWindowConstructorOptions,
} from 'electron'
import { createHash, randomUUID } from 'node:crypto'
import path from 'node:path'
import type { LoginDiagnostic } from './login-diagnostics'
import {
  isSafeLoginDiagnosticCode,
  safeAccountProbes,
  accountProbePathClasses,
  loginNavigationClass,
  loginScriptErrorClass,
} from './login-diagnostics'

import type {
  ManagementLoginCompleteInput,
  ManagementLoginCompleteResult,
  ManagementLoginIdentity,
  ManagementLoginOpenInput,
  ManagementLoginPlatform,
  ManagementLoginStatus,
  ManagementLoginStatusResult,
  ManagementLoginRefreshResult,
  ManagementLoginFocusInput,
} from '../types'
import { DouyinPlatformAuthAdapter } from './douyin-platform-auth-adapter'
import { PddPlatformAuthAdapter } from './pdd-platform-auth-adapter'
import { shouldPreserveCapturedLogin } from './management-login-lifecycle'
import {
  ManagementLoginProfileStore,
  resolveManagementLoginPartition,
} from './management-login-profile'
import type { ManagementLoginProfileMappingStore } from './management-login-profile'
import type {
  CapturedManagementSession,
  PlatformAuthAdapter,
  PlatformLoginDetectionResult,
} from './platform-auth-adapter'

interface LoginAttempt {
  attemptId: string
  correlationId: string
  platform: ManagementLoginPlatform
  teamId?: string
  appSession: Session
  partition: string
  window: BrowserWindow | null
  status: ManagementLoginStatus
  identity: ManagementLoginIdentity | null
  capturedSession: CapturedManagementSession | null
  message: string
  systemCloseRequested: boolean
  expiresAt: ReturnType<typeof setTimeout> | null
  recovery: ManagementLoginOpenInput['recovery'] | null
  recoveryShopId: string | null
  refreshFailure?: ManagementLoginStatusResult['refreshFailure']
  refreshAttemptCount: number
  rejectedCaptureFingerprint: string | null
  lastRefreshLeaseId: string | null
  profileReused: boolean
  lastPddVerificationFailureFingerprint: string | null
  lastPddVerificationFailureAt: number | null
  closeReason: LoginCloseReason | null
  navigationSequence: number
  lastProbeDiagnosticFingerprint?: string
  disposePageDiagnostics?: () => void
  finishPendingStatus?: () => void
}

type LoginCloseReason =
  | 'renderer_request'
  | 'load_failed'
  | 'app_shutdown'
  | 'attempt_timeout'
  | 'onboarding_capture'
  | 'completed_onboarding'
  | 'window_closed_without_request'

export type ManagementLoginDiagnostic = LoginDiagnostic

const LOGIN_ATTEMPT_TIMEOUT_MS = 30 * 60 * 1000
const PDD_IDENTITY_RETRY_INTERVAL_MS = 5_000
export const LOGIN_METADATA_TIMEOUT_MS = 15_000
const LOGIN_OPEN_TIMEOUT_MS = 30_000
const MAX_REFRESH_ATTEMPTS = 3

interface OnboardingApiResponse {
  shop: {
    shop_id: string
    platform_shop_id: string
    display_name: string
  }
  credential: { masked_identifier: string }
  session: {
    status: 'captured'
    version: number
    captured_at: string
  }
}

interface RefreshApiResponse {
  shop_id: string
  status: 'valid'
  version: number
  validated_at: string
  cookie_updates_applied: number
  used_cached_validation: boolean
}

interface PddIdentityApiResponse {
  platform_shop_id: string
  shop_display_name: string
}

export class ManagementLoginService {
  private readonly attempts = new Map<string, LoginAttempt>()
  private readonly shopWindows = new Map<
    string,
    { window: BrowserWindow; platform: ManagementLoginPlatform }
  >()
  private readonly polls = new Map<
    string,
    Promise<ManagementLoginStatusResult>
  >()
  private readonly refreshes = new Map<
    string,
    Promise<ManagementLoginRefreshResult>
  >()
  private readonly opens = new Map<
    string,
    {
      input: ManagementLoginOpenInput
      promise: Promise<ManagementLoginStatusResult>
    }
  >()
  private closingAll = false
  private readonly cancelledOpens = new Map<string, number>()
  private readonly createWindow: (
    options: BrowserWindowConstructorOptions,
  ) => BrowserWindow
  private readonly fromPartition: (partition: string) => Session
  private readonly backendBaseUrl: string
  private readonly allowDevTools: boolean
  private readonly profileMappingStore: ManagementLoginProfileMappingStore
  private readonly onDiagnostic?: (record: LoginDiagnostic) => void
  private readonly adapters = new Map<
    ManagementLoginPlatform,
    PlatformAuthAdapter
  >([
    ['douyin', new DouyinPlatformAuthAdapter()],
    ['pdd', new PddPlatformAuthAdapter()],
  ])

  constructor(options?: {
    backendBaseUrl?: string
    allowDevTools?: boolean
    profileMappingStore?: ManagementLoginProfileMappingStore
    createWindow?: (options: BrowserWindowConstructorOptions) => BrowserWindow
    fromPartition?: (partition: string) => Session
    adapters?: Map<ManagementLoginPlatform, PlatformAuthAdapter>
    onDiagnostic?: (record: LoginDiagnostic) => void
    metadataTimeoutMs?: number
  }) {
    this.backendBaseUrl =
      options?.backendBaseUrl ??
      process.env.CONTROL_CENTER_BACKEND_URL ??
      'http://127.0.0.1:8000/'
    this.allowDevTools = options?.allowDevTools ?? true
    this.onDiagnostic = options?.onDiagnostic
    this.metadataTimeoutMs =
      options?.metadataTimeoutMs ?? LOGIN_METADATA_TIMEOUT_MS
    this.createWindow =
      options?.createWindow ?? ((config) => new BrowserWindow(config))
    this.fromPartition =
      options?.fromPartition ??
      ((partition) => session.fromPartition(partition, { cache: true }))
    if (options?.adapters) this.adapters = options.adapters
    this.profileMappingStore =
      options?.profileMappingStore ??
      new ManagementLoginProfileStore(() =>
        path.join(app.getPath('userData'), 'management-login-profiles.json'),
      )
  }

  async focusShop(
    parent: BrowserWindow,
    input: ManagementLoginFocusInput,
  ): Promise<boolean> {
    // Current personnel authorization is checked again, including for a
    // completed browsing window. Retaining a window does not retain permission.
    const correlationId = input.correlationId ?? randomUUID()
    const started = Date.now()
    this.trace({
      correlationId,
      source: 'main',
      phase: 'focus',
      event: 'start',
    })
    let httpStatus: number | null = null
    let metadataFinished = false
    try {
      this.trace({
        correlationId,
        source: 'main',
        phase: 'session_metadata',
        event: 'start',
      })
      const result = await loginDeadline(async (signal) => {
        const headers = await this.authorizedHeaders({
          appSession: parent.webContents.session,
          teamId: input.teamId,
        })
        signal.throwIfAborted()
        this.trace({
          correlationId,
          source: 'main',
          phase: 'session_metadata',
          event: 'request',
        })
        const response = await fetch(
          this.backendUrl(`/api/v1/shops/${input.shopId}/session`),
          { headers, signal },
        )
        httpStatus = response.status
        signal.throwIfAborted()
        if (!response.ok) {
          throw new LoginOpeningError(
            response.status === 401
              ? 'AUTH_REQUIRED'
              : response.status === 403
                ? 'FORBIDDEN'
                : 'HTTP_ERROR',
          )
        }
        if (parent.isDestroyed()) throw new LoginOpeningError('CONTEXT_CHANGED')
        metadataFinished = true
        this.trace({
          correlationId,
          source: 'main',
          phase: 'session_metadata',
          event: 'finish',
          httpStatus,
          elapsedMs: Date.now() - started,
        })
        if (input.correlationId && this.isOpenCancelled(input.correlationId))
          throw new LoginOpeningError('CONTEXT_CHANGED')
        const entry = this.shopWindows.get(input.shopId)
        if (!entry || entry.window.isDestroyed()) return false
        if (entry.platform !== input.platform)
          throw new LoginOpeningError('UNEXPECTED_ERROR')
        if (entry.window.isMinimized()) entry.window.restore()
        entry.window.focus()
        return true
      }, this.metadataTimeoutMs)
      this.trace({
        correlationId,
        source: 'main',
        phase: 'focus',
        event: 'finish',
        focused: result,
        elapsedMs: Date.now() - started,
      })
      return result
    } catch (error) {
      const native = diagnosticError(error)
      const errorCode =
        error instanceof LoginOpeningError
          ? error.code
          : isSafeLoginDiagnosticCode(native.errorCode)
            ? native.errorCode
            : 'NETWORK_ERROR'
      if (!metadataFinished)
        this.trace({
          correlationId,
          source: 'main',
          phase: 'session_metadata',
          event: 'error',
          errorCode,
          httpStatus,
          errno: native.errno,
          elapsedMs: Date.now() - started,
        })
      this.trace({
        correlationId,
        source: 'main',
        phase: 'focus',
        event: 'error',
        errorCode,
        elapsedMs: Date.now() - started,
      })
      throw error instanceof LoginOpeningError
        ? error
        : new LoginOpeningError('NETWORK_ERROR')
    }
  }

  async open(
    parent: BrowserWindow,
    input: ManagementLoginOpenInput,
  ): Promise<ManagementLoginStatusResult> {
    input = { ...input, attemptId: input.attemptId ?? randomUUID() }
    const key = input.recovery
      ? input.recovery.shopId
      : (input.attemptId ?? randomUUID())
    const existing = this.opens.get(key)
    if (existing) {
      if (
        existing.input.teamId !== input.teamId ||
        existing.input.platform !== input.platform ||
        existing.input.recovery?.leaseId !== input.recovery?.leaseId ||
        existing.input.recovery?.expectedVersion !==
          input.recovery?.expectedVersion
      )
        throw new Error('登录尝试与 Session 恢复上下文不匹配')
      return existing.promise
    }
    const pending = this.openAttempt(parent, input)
    this.opens.set(key, { input, promise: pending })
    try {
      return await loginDeadline(() => pending, LOGIN_OPEN_TIMEOUT_MS)
    } catch (error) {
      void this.close(input.attemptId!).catch(() => undefined)
      throw error
    } finally {
      this.opens.delete(key)
    }
  }

  private async openAttempt(
    parent: BrowserWindow,
    input: ManagementLoginOpenInput,
  ): Promise<ManagementLoginStatusResult> {
    if (this.closingAll) throw new Error('应用正在退出')
    const adapter = this.requireAdapter(input.platform)
    const attemptId = input.attemptId ?? randomUUID()
    if (this.isOpenCancelled(attemptId))
      throw new LoginOpeningError('CONTEXT_CHANGED')
    let attempt = this.attempts.get(attemptId)
    if (attempt && attempt.platform !== input.platform) {
      throw new Error('登录尝试与平台不匹配')
    }
    if (attempt && attempt.teamId !== input.teamId) {
      throw new Error('登录尝试与当前团队不匹配')
    }
    if (!attempt) {
      const mapping = input.recovery
        ? await this.loadProfileMapping(input.recovery.shopId, input.platform)
        : null
      const profile = resolveManagementLoginPartition(attemptId, mapping)
      if (this.isOpenCancelled(attemptId))
        throw new LoginOpeningError('CONTEXT_CHANGED')
      attempt = {
        attemptId,
        correlationId: input.correlationId ?? attemptId,
        navigationSequence: 0,
        platform: input.platform,
        teamId: input.teamId,
        appSession: parent.webContents.session,
        partition: profile.partition,
        window: null,
        status: 'opened',
        identity: null,
        capturedSession: null,
        message: '登录窗口已打开，请人工完成平台登录',
        systemCloseRequested: false,
        expiresAt: null,
        recovery: input.recovery ?? null,
        recoveryShopId: input.recovery?.shopId ?? null,
        refreshAttemptCount: 0,
        rejectedCaptureFingerprint: null,
        lastRefreshLeaseId: null,
        profileReused: profile.profileReused,
        lastPddVerificationFailureFingerprint: null,
        lastPddVerificationFailureAt: null,
        closeReason: null,
      }
      this.attempts.set(attemptId, attempt)
    }
    if (this.closingAll || parent.isDestroyed()) {
      await this.close(attemptId, 'app_shutdown')
      throw new Error('应用正在退出')
    }
    if (attempt.refreshFailure) {
      // A failed refresh consumed its lease. Only an explicit open of this
      // same live attempt with a fresh, server-issued lease can arm capture.
      if (
        !attempt.refreshFailure.canContinue ||
        !input.recovery ||
        input.recovery.shopId !== attempt.recoveryShopId ||
        input.recovery.leaseId === attempt.lastRefreshLeaseId ||
        attempt.appSession !== parent.webContents.session ||
        !attempt.window ||
        attempt.window.isDestroyed() ||
        this.refreshes.has(attemptId)
      )
        throw new Error('请取消本次登录后重新打开，不能复用已失效的恢复上下文')
      attempt.recovery = input.recovery
      attempt.refreshFailure = undefined
      attempt.identity = null
      attempt.status = 'waiting'
      attempt.message = '继续检测原窗口登录状态'
    }
    if (
      attempt.recovery?.shopId !== input.recovery?.shopId ||
      attempt.recovery?.leaseId !== input.recovery?.leaseId ||
      attempt.recovery?.expectedVersion !== input.recovery?.expectedVersion
    ) {
      throw new Error('登录尝试与 Session 恢复上下文不匹配')
    }
    if (attempt.window && !attempt.window.isDestroyed()) {
      if (attempt.platform === 'pdd') {
        attempt.lastPddVerificationFailureFingerprint = null
        attempt.lastPddVerificationFailureAt = null
      }
      if (attempt.status === 'failed') {
        attempt.status = 'waiting'
        attempt.message = '重新检测登录状态'
      }
      attempt.window.focus()
      return this.toStatus(attempt)
    }

    const shopWindowKey = input.recovery ? input.recovery.shopId : null
    if (
      shopWindowKey &&
      this.shopWindows.get(shopWindowKey)?.window &&
      !this.shopWindows.get(shopWindowKey)!.window.isDestroyed()
    ) {
      await this.releaseRecoveryLease(attempt)
      this.attempts.delete(attemptId)
      throw new Error('店铺登录窗口已打开，请通过登录入口置前')
    }

    const loginSession = this.fromPartition(attempt.partition)
    loginSession.setPermissionCheckHandler(() => false)
    loginSession.setPermissionRequestHandler(
      (_webContents, _permission, callback) => callback(false),
    )
    this.report(attempt, 'open', 'start')
    const loginWindow = this.createWindow({
      title: adapter.loginWindowTitle,
      width: 1180,
      height: 820,
      minWidth: 900,
      minHeight: 640,
      parent,
      autoHideMenuBar: true,
      webPreferences: {
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true,
        webSecurity: true,
        allowRunningInsecureContent: false,
        devTools: this.allowDevTools,
        navigateOnDragDrop: false,
        webviewTag: false,
        session: loginSession,
      },
    })
    loginWindow.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
    attempt.window = loginWindow
    attempt.disposePageDiagnostics = this.installNavigationDiagnostics(
      attempt,
      loginWindow,
    )
    this.report(attempt, 'open', 'finish')
    if (shopWindowKey)
      this.shopWindows.set(shopWindowKey, {
        window: loginWindow,
        platform: input.platform,
      })
    attempt.identity = null
    attempt.lastPddVerificationFailureFingerprint = null
    attempt.lastPddVerificationFailureAt = null
    attempt.systemCloseRequested = false
    attempt.closeReason = null
    this.clearCapturedSession(attempt)
    this.armAttemptTimeout(attempt)
    attempt.status = 'waiting'
    attempt.message = '等待人工登录，系统会自动识别店铺'
    loginWindow.on('closed', () => {
      attempt!.disposePageDiagnostics?.()
      this.report(attempt!, 'close', 'closed', {
        closeReason:
          attempt!.closeReason ??
          (this.closingAll ? 'app_shutdown' : 'window_closed_without_request'),
      })
      if (
        shopWindowKey &&
        this.shopWindows.get(shopWindowKey)?.window === loginWindow
      )
        this.shopWindows.delete(shopWindowKey)
      const preserveCapture = shouldPreserveCapturedLogin({
        status: attempt!.status,
        systemCloseRequested: attempt!.systemCloseRequested,
        sessionCaptured: Boolean(attempt!.capturedSession),
      })
      attempt!.systemCloseRequested = false
      attempt!.window = null
      if (!preserveCapture && attempt!.status !== 'completed') {
        attempt!.identity = null
        attempt!.rejectedCaptureFingerprint = null
        attempt!.refreshFailure = undefined
        this.clearCapturedSession(attempt!)
        attempt!.status = 'closed'
        attempt!.message = '登录窗口已提前关闭，未采集店铺会话'
        void this.releaseRecoveryLease(attempt!)
      }
      // Page execution may never settle once its WebContents is destroyed.
      // Complete the existing IPC from the actual terminal window state.
      attempt!.finishPendingStatus?.()
    })
    try {
      this.report(attempt, 'load', 'start')
      await loginWindow.loadURL(adapter.loginUrl)
      if (this.attempts.get(attemptId) !== attempt)
        throw new LoginOpeningError('CONTEXT_CHANGED')
      this.report(attempt, 'load', 'finish')
    } catch (error) {
      this.report(attempt, 'load', 'error', diagnosticError(error))
      await this.close(attemptId, 'load_failed')
      throw error
    }
    return this.toStatus(attempt)
  }

  async getStatus(attemptId: string): Promise<ManagementLoginStatusResult> {
    const attempt = this.requireAttempt(attemptId)
    if (attempt.status !== 'waiting') return this.toStatus(attempt)
    const existing = this.polls.get(attemptId)
    if (existing) return existing
    let finishPendingStatus!: () => void
    const ended = new Promise<ManagementLoginStatusResult>((resolve) => {
      finishPendingStatus = () => resolve(this.toStatus(attempt))
    })
    attempt.finishPendingStatus = finishPendingStatus
    const pending = Promise.race([this.detectStatus(attemptId), ended])
    this.polls.set(attemptId, pending)
    try {
      return await pending
    } finally {
      if (this.polls.get(attemptId) === pending) this.polls.delete(attemptId)
      if (attempt.finishPendingStatus === finishPendingStatus)
        attempt.finishPendingStatus = undefined
    }
  }

  private async detectStatus(
    attemptId: string,
  ): Promise<ManagementLoginStatusResult> {
    const attempt = this.requireAttempt(attemptId)
    if (
      attempt.status === 'waiting' &&
      attempt.window &&
      !attempt.window.isDestroyed()
    ) {
      const loginWindow = attempt.window
      let phase: 'detect' | 'capture' = 'detect'
      try {
        const adapter = this.requireAdapter(attempt.platform)
        this.report(attempt, phase, 'start')
        const detection = await adapter.detectLoginStatus(
          loginWindow.webContents.session,
          loginWindow.webContents.id,
        )
        if (
          this.attempts.get(attemptId) !== attempt ||
          attempt.status !== 'waiting' ||
          attempt.window !== loginWindow ||
          loginWindow.isDestroyed()
        )
          return this.toStatus(attempt)
        this.reportDetection(attempt, detection)
        if (detection.readyForCapture) {
          phase = 'capture'
          this.report(attempt, phase, 'start')
          const capturedSession = await adapter.captureSession(
            loginWindow.webContents.session,
            loginWindow.webContents.id,
            detection.identity,
          )
          this.report(attempt, phase, 'finish')
          if (
            this.attempts.get(attemptId) !== attempt ||
            attempt.status !== 'waiting' ||
            attempt.window !== loginWindow ||
            loginWindow.isDestroyed()
          ) {
            capturedSession.payload.fill(0)
            return this.toStatus(attempt)
          }
          let identity = detection.identity
          if (attempt.platform === 'pdd') {
            const fingerprint = sessionFingerprint(capturedSession)
            if (
              attempt.lastPddVerificationFailureFingerprint === fingerprint &&
              attempt.lastPddVerificationFailureAt !== null &&
              Date.now() - attempt.lastPddVerificationFailureAt <
                PDD_IDENTITY_RETRY_INTERVAL_MS
            ) {
              capturedSession.payload.fill(0)
              attempt.message = '正在等待下一次拼多多店铺身份验证'
              return this.toStatus(attempt)
            }
            try {
              identity = await this.verifyPddIdentity(attempt, capturedSession)
            } catch (error) {
              capturedSession.payload.fill(0)
              if (attempt.window !== loginWindow || loginWindow.isDestroyed()) {
                return this.toStatus(attempt)
              }
              attempt.identity = null
              attempt.lastPddVerificationFailureFingerprint = fingerprint
              attempt.lastPddVerificationFailureAt = Date.now()
              attempt.status = 'waiting'
              attempt.message = `尚未通过拼多多店铺身份验证，请继续在登录窗口完成登录（${safeErrorMessage(error)}）`
              return this.toStatus(attempt)
            }
            attempt.lastPddVerificationFailureFingerprint = null
            attempt.lastPddVerificationFailureAt = null
          }
          if (!identity) {
            capturedSession.payload.fill(0)
            attempt.message = '尚未识别有效店铺身份，请继续完成平台登录'
            return this.toStatus(attempt)
          }
          if (
            attempt.recoveryShopId &&
            attempt.rejectedCaptureFingerprint ===
              recoveryFingerprint(capturedSession)
          ) {
            capturedSession.payload.fill(0)
            attempt.status = 'failed'
            attempt.identity = null
            attempt.refreshFailure = {
              code: 'candidate_rejected',
              canContinue: true,
            }
            attempt.message =
              '当前登录信息与上次被拒绝的候选相同；请在原窗口退出后重新登录，再点击继续登录'
            await this.releaseRecoveryLease(attempt)
            return this.toStatus(attempt)
          }
          if (
            this.attempts.get(attemptId) !== attempt ||
            attempt.status !== 'waiting' ||
            attempt.window !== loginWindow ||
            loginWindow.isDestroyed()
          ) {
            capturedSession.payload.fill(0)
            return this.toStatus(attempt)
          }
          this.clearCapturedSession(attempt)
          attempt.identity = identity
          attempt.capturedSession = capturedSession
          attempt.status = 'identified'
          if (attempt.recovery) {
            attempt.message = '已识别店铺，正在等待服务器验证登录状态'
          } else {
            attempt.message = '已验证店铺身份并采集登录会话，登录窗口已关闭'
            attempt.systemCloseRequested = true
            attempt.closeReason = 'onboarding_capture'
            this.report(attempt, 'close', 'request')
            loginWindow.close()
          }
        } else {
          attempt.message = detection.message
        }
      } catch (error) {
        this.report(attempt, phase, 'error', diagnosticError(error))
        if (attempt.window !== loginWindow || loginWindow.isDestroyed()) {
          return this.toStatus(attempt)
        }
        attempt.status = 'failed'
        attempt.message = safeErrorMessage(error)
      }
    }
    return this.toStatus(attempt)
  }

  async complete(
    input: ManagementLoginCompleteInput,
  ): Promise<ManagementLoginCompleteResult> {
    const attempt = this.requireAttempt(input.attemptId)
    if (attempt.recovery) throw new Error('Session 恢复不能调用首次接入命令')
    if (!attempt.capturedSession) {
      throw new Error('尚未识别有效店铺登录会话')
    }
    const response = await fetch(this.backendEndpoint(), {
      method: 'POST',
      headers: await this.authorizedHeaders(attempt),
      body: JSON.stringify({
        platform: attempt.platform,
        ...(attempt.platform === 'douyin' && attempt.identity
          ? {
              platform_shop_id: attempt.identity.platformShopId,
              shop_display_name: attempt.identity.shopDisplayName,
            }
          : {}),
        login_identifier: input.loginIdentifier.trim(),
        secret: input.secret,
        preferred_verification_channel: input.preferredVerificationChannel,
        session_payload_base64:
          attempt.capturedSession.payload.toString('base64'),
        session_captured_at: attempt.capturedSession.capturedAt,
        expected_version: 0,
        source: 'management_console',
      }),
    })
    if (!response.ok) {
      throw new Error(await safeBackendError(response))
    }
    const result = (await response.json()) as OnboardingApiResponse
    if (
      !result.shop?.shop_id ||
      !result.shop.platform_shop_id ||
      result.session?.status !== 'captured' ||
      !result.session.captured_at
    ) {
      throw new Error('服务器返回的接入结果不完整')
    }
    const profileMappingWarning =
      await this.saveProfileMappingAfterServerSuccess(
        attempt,
        result.shop.shop_id,
        '服务器已完成店铺接入',
      )
    this.finishCompletedAttempt(
      attempt,
      profileMappingWarning ?? '店铺接入成功',
    )
    return {
      shopId: result.shop.shop_id,
      platformShopId: result.shop.platform_shop_id,
      shopDisplayName: result.shop.display_name,
      maskedIdentifier: result.credential.masked_identifier,
      sessionStatus: result.session.status,
      sessionVersion: result.session.version,
      sessionCapturedAt: result.session.captured_at,
      profileMappingWarning,
    }
  }

  async refresh(attemptId: string): Promise<ManagementLoginRefreshResult> {
    const existing = this.refreshes.get(attemptId)
    if (existing) return existing
    const attempt = this.attempts.get(attemptId)
    if (attempt) this.report(attempt, 'refresh', 'start')
    const pending = this.refreshAttempt(attemptId)
    this.refreshes.set(attemptId, pending)
    try {
      const result = await pending
      if (attempt) this.report(attempt, 'refresh', 'finish')
      return result
    } catch (error) {
      if (attempt)
        this.report(attempt, 'refresh', 'error', diagnosticError(error))
      if (
        attempt &&
        this.attempts.get(attemptId) === attempt &&
        attempt.status === 'identified' &&
        attempt.window &&
        !attempt.window.isDestroyed()
      ) {
        const failure = refreshFailure(error)
        if (
          failure.code === 'candidate_rejected' ||
          failure.code === 'platform_auth_invalid'
        )
          attempt.rejectedCaptureFingerprint = attempt.capturedSession
            ? recoveryFingerprint(attempt.capturedSession)
            : null
        this.clearCapturedSession(attempt)
        attempt.identity = null
        attempt.status = 'failed'
        attempt.refreshFailure = {
          ...failure,
          canContinue:
            failure.canContinue &&
            attempt.refreshAttemptCount < MAX_REFRESH_ATTEMPTS,
        }
        attempt.message = refreshFailureMessage(attempt.refreshFailure)
        await this.releaseRecoveryLease(attempt)
      }
      throw error
    } finally {
      this.refreshes.delete(attemptId)
    }
  }

  private async refreshAttempt(
    attemptId: string,
  ): Promise<ManagementLoginRefreshResult> {
    const attempt = this.requireAttempt(attemptId)
    if (!attempt.recovery) throw new Error('当前登录尝试不是 Session 恢复')
    const recovery = attempt.recovery
    if (!attempt.capturedSession) {
      throw new Error('尚未识别有效店铺登录会话')
    }
    if (
      attempt.status !== 'identified' ||
      attempt.refreshAttemptCount >= MAX_REFRESH_ATTEMPTS
    )
      throw new Error('本次登录验证次数已用尽，请取消后重新登录')
    const headers = await this.authorizedHeaders(attempt)
    if (
      this.attempts.get(attemptId) !== attempt ||
      attempt.status !== 'identified'
    )
      throw new Error('登录同步已取消')
    attempt.refreshAttemptCount++
    attempt.lastRefreshLeaseId = recovery.leaseId
    const response = await fetch(
      this.backendUrl(`/api/v1/shops/${recovery.shopId}/session/refresh`),
      {
        method: 'POST',
        headers,
        body: JSON.stringify({
          lease_id: recovery.leaseId,
          expected_version: recovery.expectedVersion,
          session_payload_base64:
            attempt.capturedSession.payload.toString('base64'),
          captured_at: attempt.capturedSession.capturedAt,
        }),
      },
    )
    if (!response.ok) throw await refreshBackendError(response)
    const result = (await response.json()) as RefreshApiResponse
    if (
      result.shop_id !== recovery.shopId ||
      result.status !== 'valid' ||
      result.used_cached_validation !== false ||
      !Number.isInteger(result.version) ||
      result.version !== recovery.expectedVersion + 1 ||
      !result.validated_at
    ) {
      throw new Error('服务器返回的 Session 恢复结果不完整')
    }
    if (
      this.attempts.get(attemptId) !== attempt ||
      attempt.status !== 'identified'
    )
      throw new Error('登录同步已取消；服务器已完成的更新不会撤回')
    const profileMappingWarning =
      await this.saveProfileMappingAfterServerSuccess(
        attempt,
        result.shop_id,
        '服务器已恢复并验证登录会话',
      )
    if (
      this.attempts.get(attemptId) !== attempt ||
      attempt.status !== 'identified'
    )
      throw new Error('登录同步已取消；服务器已完成的更新不会撤回')
    this.finishCompletedAttempt(
      attempt,
      profileMappingWarning ?? '登录状态已更新',
      true,
    )
    return {
      shopId: result.shop_id,
      status: result.status,
      sessionVersion: result.version,
      validatedAt: result.validated_at,
      cookieUpdatesApplied: result.cookie_updates_applied,
      profileMappingWarning,
    }
  }

  async close(
    attemptId: string,
    reason: LoginCloseReason = 'renderer_request',
  ): Promise<void> {
    this.cancelledOpens.set(attemptId, Date.now())
    if (this.cancelledOpens.size > 128)
      this.cancelledOpens.delete(this.cancelledOpens.keys().next().value!)
    const attempt = this.attempts.get(attemptId)
    if (!attempt) return
    attempt.closeReason = reason
    this.report(attempt, 'close', 'request')
    attempt.disposePageDiagnostics?.()
    this.attempts.delete(attemptId)
    attempt.status = 'closed'
    if (attempt.window && !attempt.window.isDestroyed()) attempt.window.close()
    attempt.identity = null
    attempt.rejectedCaptureFingerprint = null
    attempt.refreshFailure = undefined
    this.clearCapturedSession(attempt)
    this.clearAttemptTimeout(attempt)
    const releasing = this.releaseRecoveryLease(attempt)
    attempt.finishPendingStatus?.()
    await releasing
  }

  async closeAll(): Promise<void> {
    this.closingAll = true
    const windows = [...this.shopWindows.values()]
    const closing = [...this.attempts.keys()].map((id) =>
      this.close(id, 'app_shutdown'),
    )
    // Window and capture cleanup must not wait for an offline Backend release.
    for (const { window } of windows) {
      if (!window.isDestroyed()) window.close()
    }
    this.shopWindows.clear()
    await Promise.all(closing)
  }

  private requireAdapter(
    platform: ManagementLoginPlatform,
  ): PlatformAuthAdapter {
    const adapter = this.adapters.get(platform)
    if (!adapter) throw new Error('该平台的管理端登录尚未接入')
    return adapter
  }

  private requireAttempt(attemptId: string): LoginAttempt {
    const attempt = this.attempts.get(attemptId)
    if (!attempt) throw new Error('登录尝试不存在或 Electron 已重启')
    return attempt
  }

  private toStatus(attempt: LoginAttempt): ManagementLoginStatusResult {
    return {
      attemptId: attempt.attemptId,
      status: attempt.status,
      identity: attempt.identity,
      sessionCaptured: Boolean(attempt.capturedSession),
      cookieCount: attempt.capturedSession?.cookieCount ?? 0,
      recovery: Boolean(attempt.recovery),
      profileReused: attempt.profileReused,
      message: attempt.message,
      ...(attempt.refreshFailure
        ? { refreshFailure: { ...attempt.refreshFailure } }
        : {}),
    }
  }

  private clearCapturedSession(attempt: LoginAttempt): void {
    attempt.capturedSession?.payload.fill(0)
    attempt.capturedSession = null
  }

  private finishCompletedAttempt(
    attempt: LoginAttempt,
    message: string,
    retainWindow = false,
  ): void {
    attempt.status = 'completed'
    attempt.rejectedCaptureFingerprint = null
    attempt.refreshFailure = undefined
    attempt.disposePageDiagnostics?.()
    attempt.message = message
    if (!retainWindow && attempt.window && !attempt.window.isDestroyed()) {
      attempt.systemCloseRequested = true
      attempt.closeReason = 'completed_onboarding'
      this.report(attempt, 'close', 'request')
      attempt.window.close()
    }
    this.clearCapturedSession(attempt)
    this.clearAttemptTimeout(attempt)
    attempt.recovery = null
    attempt.finishPendingStatus?.()
    this.attempts.delete(attempt.attemptId)
  }

  private armAttemptTimeout(attempt: LoginAttempt): void {
    this.clearAttemptTimeout(attempt)
    attempt.expiresAt = setTimeout(() => {
      attempt.disposePageDiagnostics?.()
      attempt.closeReason = 'attempt_timeout'
      this.report(attempt, 'close', 'request')
      if (attempt.window && !attempt.window.isDestroyed())
        attempt.window.close()
      attempt.identity = null
      this.clearCapturedSession(attempt)
      attempt.status = 'closed'
      attempt.message = '登录尝试已超时，请重新打开浏览器登录'
      attempt.expiresAt = null
      void this.releaseRecoveryLease(attempt)
      attempt.finishPendingStatus?.()
    }, LOGIN_ATTEMPT_TIMEOUT_MS)
    attempt.expiresAt.unref()
  }

  private clearAttemptTimeout(attempt: LoginAttempt): void {
    if (attempt.expiresAt) clearTimeout(attempt.expiresAt)
    attempt.expiresAt = null
  }

  private report(
    attempt: LoginAttempt,
    phase: ManagementLoginDiagnostic['phase'],
    event: ManagementLoginDiagnostic['event'],
    detail: Partial<
      Omit<
        ManagementLoginDiagnostic,
        | 'timestamp'
        | 'attemptId'
        | 'correlationId'
        | 'source'
        | 'phase'
        | 'event'
      >
    > = {},
  ): void {
    if (!this.onDiagnostic) return
    // Only code/errno and navigation state cross this diagnostic boundary.
    // Never serialize Error.message, URL, identity, cookies or platform bodies.
    let mainFrameLoading: boolean | null = null
    try {
      const window = attempt.window
      if (window && !window.isDestroyed()) {
        const contents = window.webContents
        if (contents && !contents.isDestroyed())
          mainFrameLoading = contents.isLoadingMainFrame()
      }
    } catch {
      // Native state is optional and may already be destroyed at `closed`.
      // Do not lose the lifecycle event when this one field is unavailable.
    }
    try {
      this.onDiagnostic({
        ...detail,
        timestamp: new Date().toISOString(),
        attemptId: attempt.attemptId,
        correlationId: attempt.correlationId,
        source: 'main',
        navigationSequence: attempt.navigationSequence,
        phase,
        event,
        errorCode: detail.errorCode ?? null,
        errno: detail.errno ?? null,
        isMainFrame: detail.isMainFrame ?? null,
        mainFrameLoading,
        closeReason: detail.closeReason ?? attempt.closeReason,
      })
    } catch {
      // Diagnostics may never change the original lifecycle or validation.
    }
  }

  private readonly metadataTimeoutMs: number
  private reportDetection(
    attempt: LoginAttempt,
    detection: PlatformLoginDetectionResult,
  ): void {
    try {
      this.report(attempt, 'detect', 'finish', {
        identityPresent: Boolean(detection.identity),
        captureReady: detection.readyForCapture,
        pageContextAvailable: detection.pageContextAvailable,
      })
    } catch {
      this.report(attempt, 'detect', 'finish')
    }
    try {
      const probes = safeAccountProbes(detection.probes)
      const fingerprint = JSON.stringify([
        attempt.navigationSequence,
        ...probes.map(({ probeIndex, httpStatus, requestFailed }) => [
          probeIndex,
          httpStatus,
          requestFailed,
        ]),
      ])
      if (attempt.lastProbeDiagnosticFingerprint !== fingerprint) {
        attempt.lastProbeDiagnosticFingerprint = fingerprint
        for (const probe of probes)
          this.report(
            attempt,
            'account_probe',
            probe.requestFailed ? 'error' : 'finish',
            {
              pathClass: accountProbePathClasses[probe.probeIndex],
              httpStatus: probe.httpStatus,
              elapsedMs: probe.elapsedMs,
              requestFailed: probe.requestFailed,
            },
          )
      }
    } catch {
      /* Optional probe telemetry cannot change capture or authorization. */
    }
  }
  trace(record: LoginDiagnostic): void {
    try {
      this.onDiagnostic?.({ ...record, timestamp: new Date().toISOString() })
    } catch {
      /* Observation must never change IPC or login. */
    }
  }
  private isOpenCancelled(attemptId: string): boolean {
    const cancelledAt = this.cancelledOpens.get(attemptId)
    return (
      cancelledAt !== undefined &&
      Date.now() - cancelledAt < LOGIN_ATTEMPT_TIMEOUT_MS
    )
  }

  private installNavigationDiagnostics(
    attempt: LoginAttempt,
    window: BrowserWindow,
  ): () => void {
    if (!this.onDiagnostic) return () => undefined
    const contents = window.webContents
    let scriptErrorCount = 0
    let disposed = false
    const started = (details: { isMainFrame: boolean; url: string }) => {
      if (disposed) return
      if (details.isMainFrame) {
        attempt.navigationSequence = Math.min(
          10000,
          attempt.navigationSequence + 1,
        )
        scriptErrorCount = 0
      }
      this.report(attempt, 'load', 'start', {
        isMainFrame: details.isMainFrame,
        pathClass: loginNavigationClass(details.url),
      })
    }
    const redirected = (details: { isMainFrame: boolean; url: string }) => {
      if (disposed) return
      this.report(attempt, 'load', 'redirect', {
        isMainFrame: details.isMainFrame,
        pathClass: loginNavigationClass(details.url),
      })
    }
    const finished = (_event: unknown, isMainFrame: boolean) => {
      if (disposed) return
      this.report(attempt, 'load', 'finish', { isMainFrame })
    }
    const navigated = (_event: unknown, url: string, status: number) => {
      if (disposed) return
      this.report(attempt, 'load', 'finish', {
        isMainFrame: true,
        pathClass: loginNavigationClass(url),
        httpStatus: status >= 100 && status <= 599 ? status : null,
      })
    }
    const consoleError = (details: {
      level: string
      message: string
      frame?: unknown
    }) => {
      try {
        if (disposed || details.level !== 'error' || scriptErrorCount >= 20)
          return
        scriptErrorCount++
        const errorCode = loginScriptErrorClass(details.message)
        this.report(attempt, 'script', 'error', {
          errorCode,
          scriptErrorCount,
          corsBlocked: errorCode === 'JS_CORS_POLICY',
          isMainFrame:
            Boolean(details.frame) && details.frame === contents.mainFrame,
        })
      } catch {
        /* No raw console or frame state escapes observation. */
      }
    }
    const failed = (
      _event: unknown,
      errno: number,
      _description: string,
      _url: string,
      isMainFrame: boolean,
    ) => {
      if (disposed) return
      this.report(attempt, 'load', 'error', { errno, isMainFrame })
    }
    const gone = (_event: unknown, detail: { exitCode: number }) => {
      if (disposed) return
      this.report(attempt, 'load', 'renderer_gone', { errno: detail.exitCode })
    }
    contents.on('did-start-navigation', started)
    contents.on('did-redirect-navigation', redirected)
    contents.on('did-frame-finish-load', finished)
    contents.on('did-navigate', navigated)
    contents.on('console-message', consoleError)
    contents.on('did-fail-load', failed)
    contents.on('did-fail-provisional-load', failed)
    contents.on('render-process-gone', gone)
    return () => {
      if (disposed) return
      disposed = true
      for (const detach of [
        () => contents.off('did-start-navigation', started),
        () => contents.off('did-redirect-navigation', redirected),
        () => contents.off('did-frame-finish-load', finished),
        () => contents.off('did-navigate', navigated),
        () => contents.off('console-message', consoleError),
        () => contents.off('did-fail-load', failed),
        () => contents.off('did-fail-provisional-load', failed),
        () => contents.off('render-process-gone', gone),
      ]) {
        try {
          detach()
        } catch {
          /* Diagnostic cleanup cannot prevent release/save/close. */
        }
      }
    }
  }

  private backendUrl(pathname: string): string {
    const url = new URL(pathname, this.backendBaseUrl)
    const loopback =
      url.hostname === '127.0.0.1' || url.hostname === 'localhost'
    if (url.protocol !== 'https:' && !(url.protocol === 'http:' && loopback)) {
      throw new Error('管理端登录只允许连接 HTTPS Backend 或本机 Backend')
    }
    return url.toString()
  }

  private backendEndpoint(): string {
    return this.backendUrl('/api/v1/shop-onboarding/complete')
  }

  private async verifyPddIdentity(
    attempt: LoginAttempt,
    capturedSession: CapturedManagementSession,
  ): Promise<ManagementLoginIdentity> {
    const response = await fetch(
      this.backendUrl('/api/v1/shop-onboarding/pdd/identity'),
      {
        method: 'POST',
        headers: await this.authorizedHeaders(attempt),
        body: JSON.stringify({
          session_payload_base64: capturedSession.payload.toString('base64'),
        }),
      },
    )
    if (!response.ok) throw new Error(await safeBackendError(response))
    const result = (await response.json()) as PddIdentityApiResponse
    const platformShopId = result.platform_shop_id?.trim()
    const shopDisplayName = result.shop_display_name?.trim()
    if (!platformShopId || !shopDisplayName) {
      throw new Error('服务器返回的拼多多店铺身份不完整')
    }
    return {
      platform: 'pdd',
      platformShopId,
      shopDisplayName,
    }
  }

  private async authorizedHeaders(
    attempt: Pick<LoginAttempt, 'appSession' | 'teamId'>,
  ): Promise<Record<string, string>> {
    const url = this.backendUrl('/api/v1/auth/me')
    const cookieName =
      process.env.CONTROL_CENTER_HUMAN_SESSION_COOKIE_NAME ??
      'siyu_human_session'
    const [sessionCookie] = await attempt.appSession.cookies.get({
      url,
      name: cookieName,
    })
    if (!sessionCookie) {
      throw new LoginOpeningError('AUTH_REQUIRED')
    }
    return {
      'content-type': 'application/json',
      cookie: `${sessionCookie.name}=${sessionCookie.value}`,
      ...(attempt.teamId ? { 'x-team-id': attempt.teamId } : {}),
    }
  }

  private async releaseRecoveryLease(attempt: LoginAttempt): Promise<void> {
    if (!attempt.recovery) return
    const { shopId, leaseId } = attempt.recovery
    attempt.lastRefreshLeaseId = leaseId
    attempt.recovery = null
    try {
      await fetch(
        this.backendUrl(
          `/api/v1/shops/${shopId}/session/refresh-lease/${leaseId}`,
        ),
        {
          method: 'DELETE',
          headers: await this.authorizedHeaders(attempt),
          signal: AbortSignal.timeout(10_000),
        },
      )
    } catch {
      // Lease is expiring server-side; cancellation remains best effort offline.
    }
  }

  private async loadProfileMapping(
    shopId: string,
    platform: ManagementLoginPlatform,
  ) {
    return this.profileMappingStore.load(shopId, platform)
  }

  private async saveProfileMapping(
    shopId: string,
    platform: ManagementLoginPlatform,
    partition: string,
  ): Promise<void> {
    await this.profileMappingStore.save(shopId, platform, partition)
  }

  private async saveProfileMappingAfterServerSuccess(
    attempt: LoginAttempt,
    shopId: string,
    serverSuccessMessage: string,
  ): Promise<string | null> {
    try {
      await this.saveProfileMapping(shopId, attempt.platform, attempt.partition)
      return null
    } catch (error) {
      return `${serverSuccessMessage}，但本机登录环境映射未保存；下次恢复需要重新登录（${safeErrorMessage(error)}）`
    }
  }
}

export class LoginOpeningError extends Error {
  constructor(readonly code: string) {
    // Only this fixed safe marker crosses Electron's serialized error boundary.
    super(`SHOP_LOGIN_${code}`)
  }
}

async function loginDeadline<T>(
  work: (signal: AbortSignal) => Promise<T>,
  timeoutMs: number,
): Promise<T> {
  const controller = new AbortController()
  let timer: ReturnType<typeof setTimeout>
  const expired = new Promise<never>((_resolve, reject) => {
    timer = setTimeout(() => {
      const error = new LoginOpeningError('REQUEST_TIMEOUT')
      controller.abort(error)
      reject(error)
    }, timeoutMs)
  })
  try {
    return await Promise.race([work(controller.signal), expired])
  } finally {
    clearTimeout(timer!)
  }
}

function diagnosticError(
  error: unknown,
): Pick<ManagementLoginDiagnostic, 'errorCode' | 'errno' | 'httpStatus'> {
  if (error instanceof LoginRefreshFailure)
    return { errorCode: error.code, errno: null, httpStatus: error.httpStatus }
  if (!error || typeof error !== 'object')
    return { errorCode: null, errno: null }
  try {
    const outer = error as { code?: unknown; errno?: unknown; cause?: unknown }
    const cause =
      outer.cause && typeof outer.cause === 'object'
        ? (outer.cause as { code?: unknown; errno?: unknown })
        : {}
    const code = outer.code ?? cause.code
    const errno = outer.errno ?? cause.errno
    return {
      errorCode:
        typeof code === 'string' &&
        (isSafeLoginDiagnosticCode(code) ||
          /^(?:ERR_[A-Z0-9_]{1,48})$/.test(code))
          ? code
          : null,
      errno:
        typeof errno === 'number' &&
        Number.isInteger(errno) &&
        errno >= -2147483648 &&
        errno <= 2147483647
          ? errno
          : null,
    }
  } catch {
    return { errorCode: null, errno: null }
  }
}

function sessionFingerprint(
  capturedSession: CapturedManagementSession,
): string {
  // `capturedAt` is intentionally refreshed on every capture. It must not be
  // part of the failure fingerprint, or a stable failed session would trigger
  // a new signed platform request on every status poll.
  const payload = JSON.parse(
    capturedSession.payload.toString('utf8'),
  ) as Record<string, unknown>
  delete payload.capturedAt
  return createHash('sha256')
    .update(JSON.stringify(payload))
    .digest('base64url')
}

function safeErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '登录识别失败'
}

function recoveryFingerprint(captured: CapturedManagementSession): string {
  // In-memory only. Neither this hash nor the candidate goes to diagnostics.
  try {
    return sessionFingerprint(captured)
  } catch {
    return createHash('sha256').update(captured.payload).digest('base64url')
  }
}

type RefreshFailure = NonNullable<ManagementLoginStatusResult['refreshFailure']>

class LoginRefreshFailure extends Error {
  constructor(
    readonly failure: RefreshFailure,
    readonly code: string,
    readonly httpStatus: number,
  ) {
    super(refreshFailureMessage(failure))
  }
}

function refreshFailure(error: unknown): RefreshFailure {
  if (error instanceof LoginRefreshFailure) return error.failure
  if (error instanceof LoginOpeningError && error.code === 'AUTH_REQUIRED')
    return { code: 'personnel_auth_required', canContinue: false }
  return { code: 'validation_incomplete', canContinue: true }
}

function refreshFailureMessage(failure: RefreshFailure): string {
  if (failure.code === 'personnel_auth_required')
    return '中控台人员登录已失效，原店铺会话保留；请重新登录中控台'
  if (failure.code === 'forbidden')
    return '当前店铺访问权限已变化，原会话保留；请取消登录并核对权限'
  if (!failure.canContinue) return '本次登录验证次数已用尽；请取消后重新登录'
  if (failure.code === 'candidate_rejected')
    return '本次登录信息未通过安全校验，原会话保留；请在原窗口完成正确店铺登录后点击继续登录'
  if (failure.code === 'platform_auth_invalid')
    return '本次平台登录未通过验证，原会话保留；请在原窗口重新登录后点击继续登录'
  if (failure.code === 'version_conflict')
    return '会话版本已变化；请点击继续登录，以最新版本重新验证'
  if (failure.code === 'lease_expired')
    return '本次验证租约已失效；请点击继续登录重新取得租约'
  return '本次验证未完成，结果尚未确认；请稍后点击继续登录，不会自动重试'
}

async function refreshBackendError(
  response: Response,
): Promise<LoginRefreshFailure> {
  let code: unknown
  let stage: unknown
  try {
    const body = (await response.json()) as {
      code?: unknown
      details?: { refresh_stage?: unknown }
    } | null
    code = body?.code
    stage = body?.details?.refresh_stage
  } catch {
    /* Non-JSON errors retain only the actual HTTP status. */
  }
  const stages: Record<string, string> = {
    candidate_encoding: 'REFRESH_CANDIDATE_ENCODING',
    candidate_json: 'REFRESH_CANDIDATE_JSON',
    candidate_schema: 'REFRESH_CANDIDATE_SCHEMA',
    candidate_platform: 'REFRESH_CANDIDATE_PLATFORM',
    candidate_identity: 'REFRESH_CANDIDATE_IDENTITY',
    candidate_validation: 'REFRESH_CANDIDATE_VALIDATION',
    target_changed: 'REFRESH_TARGET_CHANGED',
  }
  let failure: RefreshFailure = {
    code: 'validation_incomplete',
    canContinue: true,
  }
  let diagnosticCode = 'REFRESH_VALIDATION_INCOMPLETE'
  if (code === 'SHOP_SESSION_PAYLOAD_INVALID') {
    failure = { code: 'candidate_rejected', canContinue: true }
    diagnosticCode =
      typeof stage === 'string' && Object.hasOwn(stages, stage)
        ? stages[stage]!
        : 'REFRESH_CANDIDATE_REJECTED'
  } else if (code === 'PLATFORM_IDENTITY_MISMATCH') {
    failure = { code: 'candidate_rejected', canContinue: true }
    diagnosticCode = 'REFRESH_CANDIDATE_IDENTITY'
  } else if (code === 'AUTH_INVALID') {
    failure = { code: 'platform_auth_invalid', canContinue: true }
    diagnosticCode = 'REFRESH_AUTH_INVALID'
  } else if (response.status === 401) {
    failure = { code: 'personnel_auth_required', canContinue: false }
    diagnosticCode = 'AUTH_REQUIRED'
  } else if (response.status === 403) {
    failure = { code: 'forbidden', canContinue: false }
    diagnosticCode = 'FORBIDDEN'
  } else if (code === 'SESSION_REFRESH_LEASE_INVALID') {
    failure = { code: 'lease_expired', canContinue: true }
    diagnosticCode = 'REFRESH_LEASE_INVALID'
  } else if (code === 'SESSION_VERSION_CONFLICT') {
    failure = { code: 'version_conflict', canContinue: true }
    diagnosticCode = 'REFRESH_VERSION_CONFLICT'
  }
  return new LoginRefreshFailure(failure, diagnosticCode, response.status)
}

async function safeBackendError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { message?: unknown }
    if (typeof body.message === 'string' && body.message) return body.message
  } catch {
    // Ignore non-JSON responses and never reflect request payloads.
  }
  return `服务器未能完成店铺接入（HTTP ${response.status}）`
}
