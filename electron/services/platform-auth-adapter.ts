import type { Session } from 'electron'
import type { LoginAccountProbe } from './login-diagnostics'

import type { ManagementLoginIdentity, ManagementLoginPlatform } from '../types'

export interface CapturedManagementSession {
  payload: Buffer
  capturedAt: string
  cookieCount: number
}

export interface PlatformLoginDetectionResult {
  identity: ManagementLoginIdentity | null
  readyForCapture: boolean
  message: string
  requestFailed?: boolean
  pageContextAvailable?: boolean
  probes?: LoginAccountProbe[]
}

export interface MerchantIdentityResult {
  status: 'confirmed' | 'unverified' | 'unavailable'
  platformShopId?: string
}

export interface PlatformAuthAdapter {
  readonly platformCode: ManagementLoginPlatform
  readonly loginUrl: string
  readonly loginWindowTitle: string
  detectLoginStatus(
    session: Session,
    webContentsId: number,
  ): Promise<PlatformLoginDetectionResult>
  detectMerchantIdentity?(webContentsId: number): Promise<MerchantIdentityResult>
  merchantCookieFingerprint?(session: Session): Promise<string>
  captureSession(
    session: Session,
    webContentsId: number,
    identity: ManagementLoginIdentity | null,
    options?: { includeOriginStorage?: boolean },
  ): Promise<CapturedManagementSession>
}
