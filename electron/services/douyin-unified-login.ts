import type { BrowserWindow } from 'electron'
import type { ManagementLoginIdentity } from '../types'
import type { PlatformAuthAdapter, PlatformLoginDetectionResult } from './platform-auth-adapter'

const MERCHANT_PAGE = 'https://fxg.jinritemai.com/ffa/g/create'
const PROBE_INTERVAL_MS = 5_000

/** Existing-shop login only. The same window and partition are used throughout. */
export class DouyinUnifiedLogin {
  private phase: 'compass' | 'merchant' | 'returning' = 'compass'
  private compassIdentity: ManagementLoginIdentity | null = null
  private lastProbeKey: string | null = null
  private lastProbeAt = 0
  private loadFailed = false

  constructor(
    private readonly window: BrowserWindow,
    private readonly adapter: PlatformAuthAdapter,
    private readonly isCurrent: () => boolean,
    private readonly navigationSequence: () => number,
    private readonly isPageReady: () => boolean,
    private readonly beginNavigation: (url: string) => void,
  ) {}

  async advance(): Promise<PlatformLoginDetectionResult> {
    if (!this.isCurrent() || !this.isPageReady()) return waiting('登录页面正在加载')
    if (this.phase === 'merchant') return this.checkMerchant()
    if (this.phase === 'returning' &&
      (!this.onOrigin(this.adapter.loginUrl) || !this.isPageReady())) {
      return waiting(this.loadFailed ? '返回罗盘未完成，请关闭窗口后重试' : '正在返回罗盘，准备保存登录状态')
    }
    const navigation = this.navigationSequence()
    const detection = await this.adapter.detectLoginStatus(
      this.window.webContents.session, this.window.webContents.id,
    )
    if (!this.isCurrent() || !this.isPageReady() || this.navigationSequence() !== navigation)
      return waiting('登录页面正在跳转')
    if (!detection.readyForCapture || !detection.identity)
      return detection
    if (this.phase === 'compass') {
      this.compassIdentity = detection.identity
      this.phase = 'merchant'
      this.navigate(MERCHANT_PAGE)
      return waiting('已识别罗盘店铺，正在确认商品后台登录状态')
    }
    if (detection.identity.platformShopId !== this.compassIdentity?.platformShopId)
      return waiting('罗盘店铺发生变化，请切换回目标店铺后重新登录')
    return detection
  }

  private async checkMerchant(): Promise<PlatformLoginDetectionResult> {
    if (!this.onOrigin(MERCHANT_PAGE) || !this.isPageReady()) {
      return waiting(this.loadFailed ? '商品后台打开未完成，请关闭窗口后重试' : '正在打开商品后台；如需登录，请在当前窗口完成')
    }
    if (!this.adapter.detectMerchantIdentity || !this.adapter.merchantCookieFingerprint)
      return waiting('商品后台身份验证不可用，原登录状态保留')
    const session = this.window.webContents.session
    const navigation = this.navigationSequence()
    const before = await this.adapter.merchantCookieFingerprint(session)
    if (!this.isCurrent() || !this.isPageReady() || this.navigationSequence() !== navigation)
      return waiting('登录页面正在跳转')
    const key = `${this.navigationSequence()}:${before}`
    if (key === this.lastProbeKey || Date.now() - this.lastProbeAt < PROBE_INTERVAL_MS)
      return waiting('商品后台身份尚未确认，请按当前窗口提示操作')
    this.lastProbeAt = Date.now()
    const result = await this.adapter.detectMerchantIdentity(this.window.webContents.id)
    if (!this.isCurrent() || !this.isPageReady() || this.navigationSequence() !== navigation)
      return waiting('登录页面正在跳转')
    const after = await this.adapter.merchantCookieFingerprint(session)
    if (!this.isCurrent() || !this.isPageReady() || this.navigationSequence() !== navigation)
      return waiting('登录页面正在跳转')
    this.lastProbeKey = `${this.navigationSequence()}:${after}`
    if (result.status === 'unavailable')
      return waiting('本次商品后台验证未完成，原登录状态保留；请检查窗口后重新打开')
    if (result.status !== 'confirmed' || !result.platformShopId)
      return waiting('商品后台身份尚未确认，请按当前窗口提示操作')
    if (result.platformShopId !== this.compassIdentity?.platformShopId)
      return waiting('商品后台与罗盘不是同一家店，请在当前窗口切换到目标店铺')
    this.phase = 'returning'
    this.navigate(this.adapter.loginUrl)
    return waiting('已确认同一店铺，正在保存完整登录状态')
  }

  private onOrigin(url: string): boolean {
    try {
      return new URL(this.window.webContents.getURL()).origin === new URL(url).origin
    } catch {
      return false
    }
  }

  private navigate(url: string): void {
    if (!this.isCurrent()) return
    this.loadFailed = false
    this.beginNavigation(url)
    void this.window.loadURL(url).catch(() => {
      if (this.isCurrent() && !this.onOrigin(url)) this.loadFailed = true
    })
  }
}

function waiting(message: string): PlatformLoginDetectionResult {
  return { identity: null, readyForCapture: false, message }
}
