export type ShopSessionStatus =
  | 'not_configured'
  | 'captured'
  | 'valid'
  | 'invalid'
  | 'refresh_required'

export interface ShopSessionMetadataViewModel {
  sessionId: string | null
  configured: boolean
  status: ShopSessionStatus
  version: number
  sourceDeviceId: string | null
  sourceDeviceName: string | null
  capturedAtDisplay: string | null
  validatedAtDisplay: string | null
  expiresAtDisplay: string | null
}
