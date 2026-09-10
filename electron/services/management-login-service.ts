import { app, BrowserWindow, session, type Session } from 'electron'
import { createHash, randomUUID } from 'node:crypto'
import { promises as fs } from 'node:fs'
import path from 'node:path'

import type {
  ManagementLoginCompleteInput,
  ManagementLoginCompleteResult,
  ManagementLoginIdentity,
  ManagementLoginOpenInput,
  ManagementLoginPlatform,
  ManagementLoginStatus,
  ManagementLoginStatusResult,
  ManagementLoginRefreshResult,
} from '../types'
import { DouyinPlatformAuthAdapter } from './douyin-platform-auth-adapter'
import { PddPlatformAuthAdapter } from './pdd-platform-auth-adapter'
import { shouldPreserveCapturedLogin } from './management-login-lifecycle'
import {
  parseManagementLoginProfile,
  resolveManagementLoginPartition,
} from './management-login-profile'
import type {
  CapturedManagementSession,
  PlatformAuthAdapter,
} from './platform-auth-adapter'

interface LoginAttempt {
  attemptId: string
  platform: ManagementLoginPlatform
  teamId: string
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
  profileReused: boolean
  lastPddVerificationFailureFingerprint: string | null
  lastPddVerificationFailureAt: number | null
}

const LOGIN_ATTEMPT_TIMEOUT_MS = 30 * 60 * 1000
const PDD_IDENTITY_RETRY_INTERVAL_MS = 5_000

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
}

interface PddIdentityApiResponse {
  platform_shop_id: string
  shop_display_name: string
}

export class ManagementLoginService {
  private readonly attempts = new Map<string, LoginAttempt>()
  private readonly adapters = new Map<ManagementLoginPlatform, PlatformAuthAdapter>([
    ['douyin', new DouyinPlatformAuthAdapter()],
    ['pdd', new PddPlatformAuthAdapter()],
  ])

  async open(
    parent: BrowserWindow,
    input: ManagementLoginOpenInput,
  ): Promise<ManagementLoginStatusResult> {
    const adapter = this.requireAdapter(input.platform)
    const attemptId = input.attemptId ?? randomUUID()
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
      attempt = {
        attemptId,
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
        profileReused: profile.profileReused,
        lastPddVerificationFailureFingerprint: null,
        lastPddVerificationFailureAt: null,
      }
      this.attempts.set(attemptId, attempt)
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

    const loginSession = session.fromPartition(attempt.partition, {
      cache: true,
    })
    const loginWindow = new BrowserWindow({
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
        session: loginSession,
      },
    })
    loginWindow.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
    attempt.window = loginWindow
    attempt.identity = null
    attempt.lastPddVerificationFailureFingerprint = null
    attempt.lastPddVerificationFailureAt = null
    attempt.systemCloseRequested = false
    this.clearCapturedSession(attempt)
    this.armAttemptTimeout(attempt)
    attempt.status = 'waiting'
    attempt.message = '等待人工登录，系统会自动识别店铺'
    loginWindow.on('closed', () => {
      const preserveCapture = shouldPreserveCapturedLogin({
        status: attempt!.status,
        systemCloseRequested: attempt!.systemCloseRequested,
        sessionCaptured: Boolean(attempt!.capturedSession),
      })
      attempt!.systemCloseRequested = false
      attempt!.window = null
      if (!preserveCapture && attempt!.status !== 'completed') {
        attempt!.identity = null
        this.clearCapturedSession(attempt!)
        attempt!.status = 'closed'
        attempt!.message = '登录窗口已提前关闭，未采集店铺会话'
        void this.releaseRecoveryLease(attempt!)
      }
    })
    try {
      await loginWindow.loadURL(adapter.loginUrl)
    } catch (error) {
      await this.close(attemptId)
      throw error
    }
    return this.toStatus(attempt)
  }

  async getStatus(attemptId: string): Promise<ManagementLoginStatusResult> {
    const attempt = this.requireAttempt(attemptId)
    if (
      attempt.status === 'waiting' &&
      attempt.window &&
      !attempt.window.isDestroyed()
    ) {
      const loginWindow = attempt.window
      try {
        const adapter = this.requireAdapter(attempt.platform)
        const detection = await adapter.detectLoginStatus(
          loginWindow.webContents.session,
          loginWindow.webContents.id,
        )
        if (detection.readyForCapture) {
          const capturedSession = await adapter.captureSession(
            loginWindow.webContents.session,
            loginWindow.webContents.id,
            detection.identity,
          )
          if (
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
          attempt.message = '已验证店铺身份并采集登录会话，登录窗口已关闭'
          attempt.systemCloseRequested = true
          loginWindow.close()
        } else {
          attempt.message = detection.message
        }
      } catch (error) {
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
    await this.saveProfileMapping(
      result.shop.shop_id,
      attempt.platform,
      attempt.partition,
    )
    attempt.status = 'completed'
    attempt.message = '店铺接入成功'
    if (attempt.window && !attempt.window.isDestroyed()) {
      attempt.systemCloseRequested = true
      attempt.window.close()
    }
    this.clearCapturedSession(attempt)
    this.clearAttemptTimeout(attempt)
    this.attempts.delete(attempt.attemptId)
    return {
      shopId: result.shop.shop_id,
      platformShopId: result.shop.platform_shop_id,
      shopDisplayName: result.shop.display_name,
      maskedIdentifier: result.credential.masked_identifier,
      sessionStatus: result.session.status,
      sessionVersion: result.session.version,
      sessionCapturedAt: result.session.captured_at,
    }
  }

  async refresh(attemptId: string): Promise<ManagementLoginRefreshResult> {
    const attempt = this.requireAttempt(attemptId)
    if (!attempt.recovery) throw new Error('当前登录尝试不是 Session 恢复')
    if (!attempt.capturedSession) {
      throw new Error('尚未识别有效店铺登录会话')
    }
    const response = await fetch(
      this.backendUrl(`/api/v1/shops/${attempt.recovery.shopId}/session/refresh`),
      {
        method: 'POST',
        headers: await this.authorizedHeaders(attempt),
        body: JSON.stringify({
          lease_id: attempt.recovery.leaseId,
          expected_version: attempt.recovery.expectedVersion,
          session_payload_base64:
            attempt.capturedSession.payload.toString('base64'),
          captured_at: attempt.capturedSession.capturedAt,
        }),
      },
    )
    if (!response.ok) throw new Error(await safeBackendError(response))
    const result = (await response.json()) as RefreshApiResponse
    if (
      result.shop_id !== attempt.recovery.shopId ||
      result.status !== 'valid' ||
      !Number.isInteger(result.version) ||
      !result.validated_at
    ) {
      throw new Error('服务器返回的 Session 恢复结果不完整')
    }
    await this.saveProfileMapping(
      result.shop_id,
      attempt.platform,
      attempt.partition,
    )
    attempt.status = 'completed'
    attempt.message = '登录会话已恢复并验证有效'
    if (attempt.window && !attempt.window.isDestroyed()) {
      attempt.systemCloseRequested = true
      attempt.window.close()
    }
    this.clearCapturedSession(attempt)
    this.clearAttemptTimeout(attempt)
    this.attempts.delete(attempt.attemptId)
    return {
      shopId: result.shop_id,
      status: result.status,
      sessionVersion: result.version,
      validatedAt: result.validated_at,
      cookieUpdatesApplied: result.cookie_updates_applied,
    }
  }

  async close(attemptId: string): Promise<void> {
    const attempt = this.attempts.get(attemptId)
    if (!attempt) return
    if (attempt.window && !attempt.window.isDestroyed()) attempt.window.close()
    attempt.identity = null
    this.clearCapturedSession(attempt)
    this.clearAttemptTimeout(attempt)
    await this.releaseRecoveryLease(attempt)
    this.attempts.delete(attemptId)
  }

  async closeAll(): Promise<void> {
    await Promise.all([...this.attempts.keys()].map((id) => this.close(id)))
  }

  private requireAdapter(platform: ManagementLoginPlatform): PlatformAuthAdapter {
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
    }
  }

  private clearCapturedSession(attempt: LoginAttempt): void {
    attempt.capturedSession?.payload.fill(0)
    attempt.capturedSession = null
  }

  private armAttemptTimeout(attempt: LoginAttempt): void {
    this.clearAttemptTimeout(attempt)
    attempt.expiresAt = setTimeout(() => {
      if (attempt.window && !attempt.window.isDestroyed()) attempt.window.close()
      attempt.identity = null
      this.clearCapturedSession(attempt)
      attempt.status = 'closed'
      attempt.message = '登录尝试已超时，请重新打开浏览器登录'
      attempt.expiresAt = null
      void this.releaseRecoveryLease(attempt)
    }, LOGIN_ATTEMPT_TIMEOUT_MS)
    attempt.expiresAt.unref()
  }

  private clearAttemptTimeout(attempt: LoginAttempt): void {
    if (attempt.expiresAt) clearTimeout(attempt.expiresAt)
    attempt.expiresAt = null
  }

  private backendUrl(pathname: string): string {
    const configured =
      process.env.CONTROL_CENTER_BACKEND_URL || 'http://127.0.0.1:8000'
    const url = new URL(pathname, configured)
    const loopback = url.hostname === '127.0.0.1' || url.hostname === 'localhost'
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
    attempt: LoginAttempt,
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
      throw new Error('管理端人员登录已失效，请重新登录')
    }
    return {
      'content-type': 'application/json',
      cookie: `${sessionCookie.name}=${sessionCookie.value}`,
      'x-team-id': attempt.teamId,
    }
  }

  private async releaseRecoveryLease(attempt: LoginAttempt): Promise<void> {
    if (!attempt.recovery) return
    const { shopId, leaseId } = attempt.recovery
    attempt.recovery = null
    try {
      await fetch(
        this.backendUrl(
          `/api/v1/shops/${shopId}/session/refresh-lease/${leaseId}`,
        ),
        { method: 'DELETE', headers: await this.authorizedHeaders(attempt) },
      )
    } catch {
      // Lease is expiring server-side; cancellation remains best effort offline.
    }
  }

  private async loadProfileMapping(
    shopId: string,
    platform: ManagementLoginPlatform,
  ) {
    const filePath = path.join(
      app.getPath('userData'),
      'management-login-profiles.json',
    )
    try {
      const mappings = JSON.parse(await fs.readFile(filePath, 'utf8')) as Record<
        string,
        unknown
      >
      return parseManagementLoginProfile(mappings[shopId], platform)
    } catch {
      return null
    }
  }

  private async saveProfileMapping(
    shopId: string,
    platform: ManagementLoginPlatform,
    partition: string,
  ): Promise<void> {
    const filePath = path.join(
      app.getPath('userData'),
      'management-login-profiles.json',
    )
    let mappings: Record<string, unknown> = {}
    try {
      mappings = JSON.parse(await fs.readFile(filePath, 'utf8')) as Record<
        string,
        unknown
      >
    } catch {
      mappings = {}
    }
    mappings[shopId] = { platform, partition, updatedAt: new Date().toISOString() }
    const temporaryPath = `${filePath}.tmp`
    await fs.writeFile(temporaryPath, JSON.stringify(mappings, null, 2), 'utf8')
    await fs.rename(temporaryPath, filePath)
  }
}

function sessionFingerprint(capturedSession: CapturedManagementSession): string {
  // `capturedAt` is intentionally refreshed on every capture. It must not be
  // part of the failure fingerprint, or a stable failed session would trigger
  // a new signed platform request on every status poll.
  const payload = JSON.parse(capturedSession.payload.toString('utf8')) as Record<
    string,
    unknown
  >
  delete payload.capturedAt
  return createHash('sha256')
    .update(JSON.stringify(payload))
    .digest('base64url')
}

function safeErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '登录识别失败'
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
