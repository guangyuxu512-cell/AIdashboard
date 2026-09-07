import { webContents, type Cookie, type Session } from 'electron'

import type { ManagementLoginIdentity } from '../types'
import type {
  CapturedManagementSession,
  PlatformAuthAdapter,
  PlatformLoginDetectionResult,
} from './platform-auth-adapter'

const accountInfoUrls = [
  'https://compass.jinritemai.com/compass_api/shop/mall/common/shop_info_v2',
  'https://compass.jinritemai.com/compass_api/shop/mall/common/shop_info',
  'https://compass.jinritemai.com/auth/get_account_info',
  'https://compass.jinritemai.com/ecomauth/loginv1/get_account_info?login_source=doudian_pc_web',
  'https://fxg.jinritemai.com/ecomauth/loginv1/get_account_info?login_source=doudian_pc_web',
] as const
const acceptedCookieDomains = ['jinritemai.com'] as const

interface DouyinAccountInfoProbe {
  endpointHost: string
  status: number
  platformShopId: string
  shopDisplayName: string
  topLevelKeys: string[]
  dataKeys: string[]
  requestFailed: boolean
}

interface OriginStorageSnapshot {
  origin: string
  localStorage: Record<string, string>
  sessionStorage: Record<string, string>
}

export class DouyinPlatformAuthAdapter implements PlatformAuthAdapter {
  readonly platformCode = 'douyin' as const
  readonly loginUrl =
    'https://compass.jinritemai.com/shop/search/drainage-terms'
  readonly loginWindowTitle = '抖店登录'

  async detectLoginStatus(
    loginSession: Session,
    webContentsId: number,
  ): Promise<PlatformLoginDetectionResult> {
    const contents = webContents.fromId(webContentsId)
    if (!contents || contents.isDestroyed()) {
      return {
        identity: null,
        readyForCapture: false,
        message: '登录窗口已经关闭',
      }
    }
    const cookies = await this.getPlatformCookies(loginSession)

    // Run the verified account request inside the authenticated page context.
    // Only identity fields, HTTP status and response key names cross into Main.
    const probe = (await contents.executeJavaScript(
      `(async () => {
        try {
          const safeKeys = (value) => value && typeof value === 'object'
            ? Object.keys(value)
                .filter((key) => /^[A-Za-z0-9_]{1,64}$/.test(key))
                .slice(0, 20)
            : [];
          const readIdentity = (value, depth = 0) => {
            if (!value || typeof value !== 'object' || depth > 4) return null;
            if (Array.isArray(value)) {
              for (const item of value.slice(0, 10)) {
                const identity = readIdentity(item, depth + 1);
                if (identity) return identity;
              }
              return null;
            }
            const id = String(
              value.shop_id ?? value.shopId ?? value.account_id ?? value.accountId ?? ''
            ).trim();
            const name = String(
              value.shop_name ?? value.shopName ?? value.account_name ?? value.accountName ?? ''
            ).trim();
            if (id && name) return { platformShopId: id, shopDisplayName: name };
            for (const key of ['data', 'account_info', 'accountInfo', 'shop_info', 'shopInfo', 'current_shop', 'currentShop']) {
              const identity = readIdentity(value[key], depth + 1);
              if (identity) return identity;
            }
            return null;
          };
          let lastProbe = null;
          for (const endpoint of ${JSON.stringify(accountInfoUrls)}) {
            const response = await fetch(endpoint, {
              credentials: 'include',
              headers: { accept: 'application/json, text/plain, */*' },
            });
            const text = await response.text();
            let body = null;
            try { body = JSON.parse(text); } catch {}
            const data = body && typeof body === 'object' ? body.data : null;
            const identity = readIdentity(body);
            const platformShopId = identity?.platformShopId ?? '';
            const shopDisplayName = identity?.shopDisplayName ?? '';
            lastProbe = {
              endpointHost: new URL(endpoint).hostname,
              status: response.status,
              platformShopId,
              shopDisplayName,
              topLevelKeys: safeKeys(body),
              dataKeys: safeKeys(data),
              requestFailed: false,
            };
            if (platformShopId && shopDisplayName) return lastProbe;
          }
          return lastProbe;
        } catch {
          return {
            endpointHost: '',
            status: 0,
            platformShopId: '',
            shopDisplayName: '',
            topLevelKeys: [],
            dataKeys: [],
            requestFailed: true,
          };
        }
      })()`,
      true,
    )) as DouyinAccountInfoProbe
    const platformShopId = probe.platformShopId.trim()
    const shopDisplayName = probe.shopDisplayName.trim()
    if (platformShopId && shopDisplayName && cookies.length > 0) {
      return {
        identity: {
          platform: this.platformCode,
          platformShopId,
          shopDisplayName,
        },
        readyForCapture: true,
        message: '已从平台账号接口识别店铺',
      }
    }

    const responseShape = [...probe.topLevelKeys, ...probe.dataKeys].join(',')
    const diagnostic = probe.requestFailed
      ? '平台账号请求未完成'
      : `平台账号接口 ${probe.endpointHost} HTTP ${probe.status}${responseShape ? `，结构：${responseShape}` : ''}`
    return {
      identity: null,
      readyForCapture: false,
      message: `${diagnostic}；平台 Cookie ${cookies.length} 个，正在继续识别`,
    }
  }

  async captureSession(
    loginSession: Session,
    webContentsId: number,
    identity: ManagementLoginIdentity | null,
  ): Promise<CapturedManagementSession> {
    if (!identity) {
      throw new Error('抖店登录身份尚未识别')
    }
    const cookies = await this.getPlatformCookies(loginSession)
    if (cookies.length === 0) {
      throw new Error('抖店登录会话尚未完整建立')
    }
    const contents = webContents.fromId(webContentsId)
    if (!contents || contents.isDestroyed()) {
      throw new Error('登录窗口已经关闭')
    }
    // Fixed adapter-owned script. Renderer cannot supply JavaScript or inspect its result.
    const storage = (await contents.executeJavaScript(
      `(() => {
        const copy = (storage) => {
          const result = {};
          for (let index = 0; index < storage.length; index += 1) {
            const key = storage.key(index);
            if (key) result[key] = storage.getItem(key) ?? '';
          }
          return result;
        };
        return {
          origin: location.origin,
          localStorage: copy(window.localStorage),
          sessionStorage: copy(window.sessionStorage),
        };
      })()`,
      true,
    )) as OriginStorageSnapshot
    const capturedAt = new Date().toISOString()
    const payload = Buffer.from(
      JSON.stringify({
        schema: 'management-login.session.v1',
        platform: this.platformCode,
        identity,
        capturedAt,
        cookies: cookies.map(toSerializableCookie),
        storage,
      }),
      'utf8',
    )
    return { payload, capturedAt, cookieCount: cookies.length }
  }

  private async getPlatformCookies(loginSession: Session): Promise<Cookie[]> {
    const cookies = await loginSession.cookies.get({})
    return cookies.filter((cookie) => {
      const domain = (cookie.domain ?? '').replace(/^\./, '').toLowerCase()
      return acceptedCookieDomains.some(
        (accepted) => domain === accepted || domain.endsWith(`.${accepted}`),
      )
    })
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
