export type DesktopResolvedTheme = 'light' | 'dark'
export type ManagementLoginPlatform = 'douyin' | 'pdd'
export type ManagementLoginStatus =
  'opened' | 'waiting' | 'identified' | 'closed' | 'failed' | 'completed'

export interface ManagementLoginIdentity {
  platform: ManagementLoginPlatform
  platformShopId: string
  shopDisplayName: string
}

export interface ManagementLoginOpenInput {
  platform: ManagementLoginPlatform
  teamId?: string
  attemptId?: string
  correlationId?: string
  recovery?: {
    shopId: string
    leaseId: string
    expectedVersion: number
  }
}

export interface ManagementLoginFocusInput {
  platform: ManagementLoginPlatform
  teamId?: string
  shopId: string
  correlationId?: string
}

export interface ManagementLoginStatusResult {
  attemptId: string
  status: ManagementLoginStatus
  identity: ManagementLoginIdentity | null
  sessionCaptured: boolean
  cookieCount: number
  recovery: boolean
  profileReused: boolean
  message: string
  refreshFailure?: {
    code:
      | 'candidate_rejected'
      | 'identity_mismatch'
      | 'platform_auth_invalid'
      | 'lease_expired'
      | 'version_conflict'
      | 'personnel_auth_required'
      | 'forbidden'
      | 'validation_incomplete'
    canContinue: boolean
  }
}

export interface ManagementLoginCompleteInput {
  attemptId: string
  loginIdentifier: string
  secret: string
  preferredVerificationChannel: 'manual' | 'email' | 'sms_hardware'
}

export interface ManagementLoginCompleteResult {
  shopId: string
  platformShopId: string
  shopDisplayName: string
  maskedIdentifier: string
  sessionStatus: 'captured'
  sessionVersion: number
  sessionCapturedAt: string
  profileMappingWarning: string | null
}

export interface ManagementLoginRefreshResult {
  shopId: string
  status: 'valid'
  sessionVersion: number
  validatedAt: string
  cookieUpdatesApplied: number
  profileMappingWarning: string | null
}

export const desktopIpcChannels = {
  setTitleBarTheme: 'appearance:set-title-bar-theme',
  openManagementLogin: 'management-login:open',
  focusManagementShop: 'management-login:focus-shop',
  getManagementLoginStatus: 'management-login:get-status',
  completeManagementLogin: 'management-login:complete',
  refreshManagementLogin: 'management-login:refresh',
  closeManagementLogin: 'management-login:close',
} as const

export interface DesktopApi {
  appearance: {
    setTitleBarTheme(theme: DesktopResolvedTheme): void
  }
  managementLogin: {
    readonly correlationSupported?: true
    readonly globalShopLoginSupported?: true
    readonly refreshRecoverySupported?: true
    focusShop(input: ManagementLoginFocusInput): Promise<boolean>
    open(input: ManagementLoginOpenInput): Promise<ManagementLoginStatusResult>
    getStatus(attemptId: string): Promise<ManagementLoginStatusResult>
    complete(
      input: ManagementLoginCompleteInput,
    ): Promise<ManagementLoginCompleteResult>
    refresh(attemptId: string): Promise<ManagementLoginRefreshResult>
    close(attemptId: string): Promise<void>
  }
}

export function isManagementLoginFocusInput(
  value: unknown,
): value is ManagementLoginFocusInput {
  if (!value || typeof value !== 'object') return false
  const input = value as Record<string, unknown>
  return (
    hasOnlyKeys(input, ['platform', 'teamId', 'shopId', 'correlationId']) &&
    isManagementLoginPlatform(input.platform) &&
    (input.teamId === undefined || isUuid(input.teamId)) &&
    isUuid(input.shopId) &&
    (input.correlationId === undefined || isUuid(input.correlationId))
  )
}

export function isDesktopResolvedTheme(
  value: unknown,
): value is DesktopResolvedTheme {
  return value === 'light' || value === 'dark'
}

export function isManagementLoginPlatform(
  value: unknown,
): value is ManagementLoginPlatform {
  return value === 'douyin' || value === 'pdd'
}

export function isManagementLoginOpenInput(
  value: unknown,
): value is ManagementLoginOpenInput {
  if (!value || typeof value !== 'object') return false
  const input = value as Record<string, unknown>
  return (
    hasOnlyKeys(input, [
      'platform',
      'teamId',
      'attemptId',
      'correlationId',
      'recovery',
    ]) &&
    isManagementLoginPlatform(input.platform) &&
    (isUuid(input.teamId) ||
      (input.teamId === undefined && input.recovery !== undefined)) &&
    (input.attemptId === undefined || isUuid(input.attemptId)) &&
    (input.correlationId === undefined || isUuid(input.correlationId)) &&
    (input.recovery === undefined || isManagementLoginRecovery(input.recovery))
  )
}

function isManagementLoginRecovery(value: unknown): boolean {
  if (!value || typeof value !== 'object') return false
  const recovery = value as Record<string, unknown>
  return (
    hasOnlyKeys(recovery, ['shopId', 'leaseId', 'expectedVersion']) &&
    isUuid(recovery.shopId) &&
    isUuid(recovery.leaseId) &&
    Number.isInteger(recovery.expectedVersion) &&
    Number(recovery.expectedVersion) >= 1
  )
}

export function isManagementLoginCompleteInput(
  value: unknown,
): value is ManagementLoginCompleteInput {
  if (!value || typeof value !== 'object') return false
  const input = value as Record<string, unknown>
  return (
    hasOnlyKeys(input, [
      'attemptId',
      'loginIdentifier',
      'secret',
      'preferredVerificationChannel',
    ]) &&
    isUuid(input.attemptId) &&
    typeof input.loginIdentifier === 'string' &&
    input.loginIdentifier.trim().length > 0 &&
    input.loginIdentifier.length <= 320 &&
    typeof input.secret === 'string' &&
    input.secret.length > 0 &&
    input.secret.length <= 1000 &&
    (input.preferredVerificationChannel === 'manual' ||
      input.preferredVerificationChannel === 'email' ||
      input.preferredVerificationChannel === 'sms_hardware')
  )
}

export function isUuid(value: unknown): value is string {
  return (
    typeof value === 'string' &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      value,
    )
  )
}

function hasOnlyKeys(
  value: Record<string, unknown>,
  allowedKeys: readonly string[],
): boolean {
  const allowed = new Set(allowedKeys)
  return Object.keys(value).every((key) => allowed.has(key))
}
