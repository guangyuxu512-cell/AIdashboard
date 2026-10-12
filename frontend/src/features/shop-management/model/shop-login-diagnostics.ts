import { ApiError } from '@/shared/api'

export const LOGIN_FOCUS_TIMEOUT_MS = 20_000
export const LOGIN_LEASE_TIMEOUT_MS = 20_000
export const LOGIN_OPEN_TIMEOUT_MS = 35_000
const prefix = '[shop-login-trace] '

export type LoginOpeningPhase = 'entry' | 'focus' | 'lease' | 'open' | 'cleanup'
export type LoginOpeningCode =
  | 'REQUEST_TIMEOUT'
  | 'AUTH_REQUIRED'
  | 'FORBIDDEN'
  | 'HTTP_ERROR'
  | 'NETWORK_ERROR'
  | 'IPC_ERROR'
  | 'UNEXPECTED_ERROR'
  | 'CONTEXT_CHANGED'

export class LoginOpeningFailure extends Error {
  constructor(readonly code: LoginOpeningCode) {
    super(code)
  }
}

export function openingErrorCode(error: unknown): LoginOpeningCode {
  if (error instanceof LoginOpeningFailure) return error.code
  if (error instanceof ApiError) {
    if (error.code === 'REQUEST_TIMEOUT') return 'REQUEST_TIMEOUT'
    if (error.status === 401) return 'AUTH_REQUIRED'
    if (error.status === 403) return 'FORBIDDEN'
    return error.status ? 'HTTP_ERROR' : 'NETWORK_ERROR'
  }
  // Electron serializes native errors as text. Recognize only our fixed
  // marker; never log the supplied message or reflect it into the UI.
  if (error instanceof Error) {
    for (const code of [
      'REQUEST_TIMEOUT',
      'AUTH_REQUIRED',
      'FORBIDDEN',
      'HTTP_ERROR',
      'CONTEXT_CHANGED',
    ] as const)
      if (error.message.includes(`SHOP_LOGIN_${code}`)) return code
  }
  return 'IPC_ERROR'
}

export function openingFailureMessage(error: unknown): string {
  switch (openingErrorCode(error)) {
    case 'REQUEST_TIMEOUT':
      return '打开店铺登录超时，原登录状态保留；请稍后重试'
    case 'AUTH_REQUIRED':
      return '中控台人员登录已失效，请重新登录中控台'
    case 'FORBIDDEN':
      return '当前店铺访问权限已变化，请刷新列表后核对权限'
    default:
      return '本次打开未完成，原登录状态保留；请稍后重试'
  }
}

export function reportLoginStage(
  correlationId: string,
  phase: LoginOpeningPhase,
  event: 'start' | 'finish' | 'error' | 'blocked' | 'duplicate',
  details: {
    errorCode?: string
    httpStatus?: number | null
    elapsedMs?: number
    bridgeAvailable?: boolean
    superAccount?: boolean
    teamSelected?: boolean
    platformSupported?: boolean
    focused?: boolean
  } = {},
): void {
  try {
    console.info(
      prefix +
        JSON.stringify({
          correlationId,
          source: 'renderer',
          phase,
          event,
          ...details,
        }),
    )
  } catch {
    /* Diagnostics cannot interrupt opening or cleanup. */
  }
}

export function waitForLoginOpening<T>(
  pending: Promise<T>,
  timeoutMs: number,
  signal?: AbortSignal,
): Promise<T> {
  return new Promise((resolve, reject) => {
    let settled = false
    const finish = (accept: () => void) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      signal?.removeEventListener('abort', abort)
      accept()
    }
    const abort = () =>
      finish(() => reject(new LoginOpeningFailure('CONTEXT_CHANGED')))
    const timer = setTimeout(
      () => finish(() => reject(new LoginOpeningFailure('REQUEST_TIMEOUT'))),
      timeoutMs,
    )
    pending.then(
      (result) => finish(() => resolve(result)),
      (error) => finish(() => reject(error)),
    )
    if (signal?.aborted) abort()
    else signal?.addEventListener('abort', abort, { once: true })
  })
}
