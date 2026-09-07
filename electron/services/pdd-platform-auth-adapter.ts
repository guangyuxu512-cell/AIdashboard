import { type Cookie, type Session } from 'electron'

import type { ManagementLoginIdentity } from '../types'
import type {
  CapturedManagementSession,
  PlatformAuthAdapter,
  PlatformLoginDetectionResult,
} from './platform-auth-adapter'

// Cookie capture must match the exact PDD endpoint that the backend calls to
// verify the merchant. A root-path query omits cookies with a narrower path
// scope such as `/earth`.
const pddMerchantIdentityUrl =
  'https://mms.pinduoduo.com/earth/api/merchant/queryMerchantInfoByMallId'

// These are present in the manually verified PDD management session, while an
// unauthenticated PDD window only receives generic device/browser cookies.
// They only gate the server preflight; the identity API remains the authority.
const pddAuthenticatedCookieNames = new Set(['JSESSIONID', 'PASS_ID'])

export class PddPlatformAuthAdapter implements PlatformAuthAdapter {
  readonly platformCode = 'pdd' as const
  readonly loginUrl = 'https://mms.pinduoduo.com/home'
  readonly loginWindowTitle = '拼多多登录'

  async detectLoginStatus(
    loginSession: Session,
    _webContentsId: number,
  ): Promise<PlatformLoginDetectionResult> {
    const cookies = await this.getIdentityCookies(loginSession)
    if (!hasAuthenticatedPddSession(cookies)) {
      return {
        identity: null,
        readyForCapture: false,
        message: '尚未检测到拼多多管理端有效登录会话',
      }
    }
    return {
      identity: null,
      readyForCapture: true,
      message: '已采集拼多多管理端会话，确认接入时将由服务器验证店铺身份',
    }
  }

  async captureSession(
    loginSession: Session,
    _webContentsId: number,
    identity: ManagementLoginIdentity | null,
  ): Promise<CapturedManagementSession> {
    const cookies = await this.getIdentityCookies(loginSession)
    if (!hasAuthenticatedPddSession(cookies)) {
      throw new Error('拼多多登录会话尚未完整建立')
    }
    const capturedAt = new Date().toISOString()
    const payload = Buffer.from(
      JSON.stringify({
        schema: 'management-login.session.v1',
        platform: this.platformCode,
        ...(identity ? { identity } : {}),
        capturedAt,
        cookies: cookies.map(toSerializableCookie),
      }),
      'utf8',
    )
    return { payload, capturedAt, cookieCount: cookies.length }
  }

  private getIdentityCookies(loginSession: Session): Promise<Cookie[]> {
    // Electron scopes this query to cookies applicable to the actual identity
    // endpoint, including any PDD cookies whose path is narrower than `/`.
    return loginSession.cookies.get({ url: pddMerchantIdentityUrl })
  }
}

function hasAuthenticatedPddSession(cookies: Cookie[]): boolean {
  const names = new Set(cookies.map((cookie) => cookie.name))
  return [...pddAuthenticatedCookieNames].every((name) => names.has(name))
}

function toSerializableCookie(cookie: Cookie): Record<string, unknown> {
  return {
    name: cookie.name,
    value: cookie.value,
    domain: cookie.domain,
    path: cookie.path,
    secure: cookie.secure,
    httpOnly: cookie.httpOnly,
    sameSite: cookie.sameSite,
    expirationDate: cookie.expirationDate,
  }
}
