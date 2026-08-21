import { app, BrowserWindow, session } from 'electron'
import { randomUUID } from 'node:crypto'
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
} from '../types'
import { DouyinPlatformAuthAdapter } from './douyin-platform-auth-adapter'
import type {
  CapturedManagementSession,
  PlatformAuthAdapter,
} from './platform-auth-adapter'

interface LoginAttempt {
  attemptId: string
  platform: ManagementLoginPlatform
  partition: string
  window: BrowserWindow | null
  status: ManagementLoginStatus
  identity: ManagementLoginIdentity | null
  capturedSession: CapturedManagementSession | null
  message: string
}

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

export class ManagementLoginService {
  private readonly attempts = new Map<string, LoginAttempt>()
  private readonly adapters = new Map<ManagementLoginPlatform, PlatformAuthAdapter>([
    ['douyin', new DouyinPlatformAuthAdapter()],
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
    if (!attempt) {
      attempt = {
        attemptId,
        platform: input.platform,
        partition: `persist:management-login-${attemptId}`,
        window: null,
        status: 'opened',
        identity: null,
        capturedSession: null,
        message: '登录窗口已打开，请人工完成平台登录',
      }
      this.attempts.set(attemptId, attempt)
    }
    if (attempt.window && !attempt.window.isDestroyed()) {
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
      title: '抖店登录',
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
    this.clearCapturedSession(attempt)
    attempt.status = 'waiting'
    attempt.message = '等待人工登录，系统会自动识别店铺'
    loginWindow.on('closed', () => {
      if (attempt?.status !== 'completed') {
        attempt!.status = 'closed'
        attempt!.message = '登录窗口已关闭，尚未完成接入'
      }
      attempt!.window = null
    })
    await loginWindow.loadURL(adapter.loginUrl)
    return this.toStatus(attempt)
  }

  async getStatus(attemptId: string): Promise<ManagementLoginStatusResult> {
    const attempt = this.requireAttempt(attemptId)
    if (
      attempt.status === 'waiting' &&
      attempt.window &&
      !attempt.window.isDestroyed()
    ) {
      try {
        const adapter = this.requireAdapter(attempt.platform)
        const detection = await adapter.detectLoginStatus(
          attempt.window.webContents.session,
          attempt.window.webContents.id,
        )
        if (detection.identity) {
          const capturedSession = await adapter.captureSession(
            attempt.window.webContents.session,
            attempt.window.webContents.id,
            detection.identity,
          )
          this.clearCapturedSession(attempt)
          attempt.identity = detection.identity
          attempt.capturedSession = capturedSession
          attempt.status = 'identified'
          attempt.message = '已自动识别店铺并采集登录会话，请确认后完成接入'
        } else {
          attempt.message = detection.message
        }
      } catch (error) {
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
    if (!attempt.identity || !attempt.capturedSession) {
      throw new Error('尚未识别有效店铺登录会话')
    }
    const response = await fetch(this.backendEndpoint(), {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        platform: attempt.identity.platform,
        platform_shop_id: attempt.identity.platformShopId,
        shop_display_name: attempt.identity.shopDisplayName,
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
    if (attempt.window && !attempt.window.isDestroyed()) attempt.window.close()
    this.clearCapturedSession(attempt)
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

  async close(attemptId: string): Promise<void> {
    const attempt = this.attempts.get(attemptId)
    if (!attempt) return
    if (attempt.window && !attempt.window.isDestroyed()) attempt.window.close()
    this.clearCapturedSession(attempt)
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
      message: attempt.message,
    }
  }

  private clearCapturedSession(attempt: LoginAttempt): void {
    attempt.capturedSession?.payload.fill(0)
    attempt.capturedSession = null
  }

  private backendEndpoint(): string {
    const configured =
      process.env.CONTROL_CENTER_BACKEND_URL || 'http://127.0.0.1:8000'
    const url = new URL('/api/v1/shop-onboarding/complete', configured)
    const loopback = url.hostname === '127.0.0.1' || url.hostname === 'localhost'
    if (url.protocol !== 'https:' && !(url.protocol === 'http:' && loopback)) {
      throw new Error('管理端登录只允许连接 HTTPS Backend 或本机 Backend')
    }
    return url.toString()
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
