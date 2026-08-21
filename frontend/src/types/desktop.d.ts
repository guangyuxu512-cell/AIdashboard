declare global {
  type ManagementLoginStatus =
    | 'opened'
    | 'waiting'
    | 'identified'
    | 'closed'
    | 'failed'
    | 'completed'

  interface ManagementLoginStatusResult {
    attemptId: string
    status: ManagementLoginStatus
    identity: {
      platform: 'douyin'
      platformShopId: string
      shopDisplayName: string
    } | null
    sessionCaptured: boolean
    cookieCount: number
    recovery: boolean
    profileReused: boolean
    message: string
  }

  interface ManagementLoginCompleteResult {
    shopId: string
    platformShopId: string
    shopDisplayName: string
    maskedIdentifier: string
    sessionStatus: 'captured'
    sessionVersion: number
    sessionCapturedAt: string
  }

  interface Window {
    desktop?: {
      appearance: {
        setTitleBarTheme(theme: 'light' | 'dark'): void
      }
      managementLogin?: {
        open(input: {
          platform: 'douyin'
          attemptId?: string
          recovery?: {
            shopId: string
            leaseId: string
            expectedVersion: number
          }
        }): Promise<ManagementLoginStatusResult>
        getStatus(attemptId: string): Promise<ManagementLoginStatusResult>
        complete(input: {
          attemptId: string
          loginIdentifier: string
          secret: string
          preferredVerificationChannel: 'manual' | 'email' | 'sms_hardware'
        }): Promise<ManagementLoginCompleteResult>
        refresh(attemptId: string): Promise<{
          shopId: string
          status: 'valid'
          sessionVersion: number
          validatedAt: string
          cookieUpdatesApplied: number
        }>
        close(attemptId: string): Promise<void>
      }
    }
  }
}

export {}
