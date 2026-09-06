export type DesktopResolvedTheme = 'light' | 'dark'
export type ManagementLoginPlatform = 'douyin'
export type ManagementLoginStatus =
  | 'opened'
  | 'waiting'
  | 'identified'
  | 'closed'
  | 'failed'
  | 'completed'

export interface ManagementLoginIdentity {
  platform: ManagementLoginPlatform
  platformShopId: string
  shopDisplayName: string
}

export interface ManagementLoginOpenInput {
  platform: ManagementLoginPlatform
  teamId: string
  attemptId?: string
  recovery?: {
    shopId: string
    leaseId: string
    expectedVersion: number
  }
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
}

export interface ManagementLoginRefreshResult {
  shopId: string
  status: 'valid'
  sessionVersion: number
  validatedAt: string
  cookieUpdatesApplied: number
}

export const desktopIpcChannels = {
  setTitleBarTheme: 'appearance:set-title-bar-theme',
  openManagementLogin: 'management-login:open',
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
    open(input: ManagementLoginOpenInput): Promise<ManagementLoginStatusResult>
    getStatus(attemptId: string): Promise<ManagementLoginStatusResult>
    complete(
      input: ManagementLoginCompleteInput,
    ): Promise<ManagementLoginCompleteResult>
    refresh(attemptId: string): Promise<ManagementLoginRefreshResult>
    close(attemptId: string): Promise<void>
  }
}

export function isDesktopResolvedTheme(
  value: unknown,
): value is DesktopResolvedTheme {
  return value === 'light' || value === 'dark'
}

export function isManagementLoginPlatform(
  value: unknown,
): value is ManagementLoginPlatform {
  return value === 'douyin'
}

export function isManagementLoginOpenInput(
  value: unknown,
): value is ManagementLoginOpenInput {
  if (!value || typeof value !== 'object') return false
  const input = value as Record<string, unknown>
  return (
    hasOnlyKeys(input, ['platform', 'teamId', 'attemptId', 'recovery']) &&
    isManagementLoginPlatform(input.platform) &&
    isUuid(input.teamId) &&
    (input.attemptId === undefined || isUuid(input.attemptId)) &&
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
