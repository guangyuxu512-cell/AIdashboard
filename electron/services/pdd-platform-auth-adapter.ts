import { type Cookie, type Session } from 'electron'

import type { ManagementLoginIdentity } from '../types'
import type {
  CapturedManagementSession,
  PlatformAuthAdapter,
  PlatformLoginDetectionResult,
} from './platform-auth-adapter'

const pddSessionUrl = 'https://mms.pinduoduo.com/'

export class PddPlatformAuthAdapter implements PlatformAuthAdapter {
  readonly platformCode = 'pdd' as const
  readonly loginUrl = 'https://mms.pinduoduo.com/home'
  readonly loginWindowTitle = '拼多多登录'

  async detectLoginStatus(
    loginSession: Session,
    _webContentsId: number,
  ): Promise<PlatformLoginDetectionResult> {
    const cookies = await this.getMmsCookies(loginSession)
    if (cookies.length === 0) {
      return {
        identity: null,
        readyForCapture: false,
        message: '尚未检测到适用于拼多多管理端的登录会话',
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
    const cookies = await this.getMmsCookies(loginSession)
    if (cookies.length === 0) {
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

  private getMmsCookies(loginSession: Session): Promise<Cookie[]> {
    // Electron scopes this query to cookies applicable to the PDD management host.
    return loginSession.cookies.get({ url: pddSessionUrl })
  }
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
