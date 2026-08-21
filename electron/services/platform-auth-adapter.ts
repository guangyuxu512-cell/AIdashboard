import type { Session } from 'electron'

import type {
  ManagementLoginIdentity,
  ManagementLoginPlatform,
} from '../types'

export interface CapturedManagementSession {
  payload: Buffer
  capturedAt: string
  cookieCount: number
}

export interface PlatformLoginDetectionResult {
  identity: ManagementLoginIdentity | null
  message: string
}

export interface PlatformAuthAdapter {
  readonly platformCode: ManagementLoginPlatform
  readonly loginUrl: string
  detectLoginStatus(
    session: Session,
    webContentsId: number,
  ): Promise<PlatformLoginDetectionResult>
  captureSession(
    session: Session,
    webContentsId: number,
    identity: ManagementLoginIdentity,
  ): Promise<CapturedManagementSession>
}
