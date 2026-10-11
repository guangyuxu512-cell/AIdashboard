import { appendFile, mkdir, rename, rm, stat } from 'node:fs/promises'
import path from 'node:path'
import type { WebContents } from 'electron'
import { isTrustedRendererUrl } from '../config/runtime'
import { isUuid } from '../types'

export const rendererLoginDiagnosticPrefix = '[shop-login-trace] '
const phases = [
  'entry',
  'focus_ipc',
  'focus',
  'session_metadata',
  'lease',
  'open_ipc',
  'open',
  'load',
  'detect',
  'capture',
  'refresh',
  'close',
  'cleanup',
] as const
const events = [
  'start',
  'finish',
  'error',
  'blocked',
  'duplicate',
  'redirect',
  'request',
  'closed',
  'renderer_gone',
] as const
const reasons = [
  'renderer_request',
  'load_failed',
  'app_shutdown',
  'attempt_timeout',
  'onboarding_capture',
  'completed_onboarding',
  'window_closed_without_request',
] as const
const errorCodes = new Set([
  'REQUEST_TIMEOUT',
  'AUTH_REQUIRED',
  'FORBIDDEN',
  'HTTP_ERROR',
  'NETWORK_ERROR',
  'IPC_ERROR',
  'UNEXPECTED_ERROR',
  'NO_BRIDGE',
  'NO_TEAM',
  'NOT_ALLOWED',
  'UNSUPPORTED_PLATFORM',
  'CONTEXT_CHANGED',
  'ERR_ABORTED',
  'ERR_FAILED',
  'ERR_NAME_NOT_RESOLVED',
  'ERR_CONNECTION_REFUSED',
  'ERR_CONNECTION_RESET',
  'ERR_CONNECTION_TIMED_OUT',
  'ERR_TIMED_OUT',
  'ERR_INTERNET_DISCONNECTED',
  'ENOENT',
  'EACCES',
  'ECONNRESET',
  'ETIMEDOUT',
  'ENOTFOUND',
  'EAI_AGAIN',
  'ECONNREFUSED',
  'EHOSTUNREACH',
  'UND_ERR_CONNECT_TIMEOUT',
  'UND_ERR_HEADERS_TIMEOUT',
  'UND_ERR_SOCKET',
  'ERR_TLS_CERT_ALTNAME_INVALID',
  'CERT_HAS_EXPIRED',
  'DEPTH_ZERO_SELF_SIGNED_CERT',
  'UNABLE_TO_VERIFY_LEAF_SIGNATURE',
  'ERR_CERT_AUTHORITY_INVALID',
  'ERR_CERT_DATE_INVALID',
])
export function isSafeLoginDiagnosticCode(code: unknown): code is string {
  return typeof code === 'string' && errorCodes.has(code)
}
const booleanKeys = [
  'bridgeAvailable',
  'superAccount',
  'teamSelected',
  'platformSupported',
  'focused',
  'isMainFrame',
  'mainFrameLoading',
] as const
const allowedKeys = new Set([
  'timestamp',
  'correlationId',
  'attemptId',
  'source',
  'phase',
  'event',
  'errorCode',
  'errno',
  'httpStatus',
  'elapsedMs',
  'closeReason',
  ...booleanKeys,
])

export interface LoginDiagnostic {
  timestamp?: string
  correlationId: string
  attemptId?: string
  source: 'renderer' | 'ipc' | 'main'
  phase: (typeof phases)[number]
  event: (typeof events)[number]
  errorCode?: string | null
  errno?: number | null
  httpStatus?: number | null
  elapsedMs?: number | null
  closeReason?: (typeof reasons)[number] | null
  bridgeAvailable?: boolean | null
  superAccount?: boolean | null
  teamSelected?: boolean | null
  platformSupported?: boolean | null
  focused?: boolean | null
  isMainFrame?: boolean | null
  mainFrameLoading?: boolean | null
}

// Rebuild every record. Unknown keys, invalid values, raw errors and long
// console messages are discarded; this is observation, never authorization.
export function safeLoginDiagnostic(
  value: unknown,
  keepTimestamp = false,
): LoginDiagnostic | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const input = value as Record<string, unknown>
  if (Object.keys(input).some((key) => !allowedKeys.has(key))) return null
  if (
    !isUuid(input.correlationId) ||
    !['renderer', 'ipc', 'main'].includes(String(input.source)) ||
    !phases.includes(input.phase as (typeof phases)[number]) ||
    !events.includes(input.event as (typeof events)[number])
  )
    return null
  if (input.attemptId !== undefined && !isUuid(input.attemptId)) return null
  if (
    input.timestamp !== undefined &&
    (typeof input.timestamp !== 'string' ||
      input.timestamp.length > 32 ||
      !Number.isFinite(Date.parse(input.timestamp)))
  )
    return null
  const record: LoginDiagnostic = {
    timestamp:
      keepTimestamp && typeof input.timestamp === 'string'
        ? new Date(input.timestamp).toISOString()
        : new Date().toISOString(),
    correlationId: input.correlationId,
    source: input.source as LoginDiagnostic['source'],
    phase: input.phase as LoginDiagnostic['phase'],
    event: input.event as LoginDiagnostic['event'],
  }
  if (input.attemptId !== undefined)
    record.attemptId = input.attemptId as string
  for (const key of booleanKeys) {
    const item = input[key]
    if (item !== undefined && item !== null && typeof item !== 'boolean')
      return null
    if (item !== undefined) record[key] = item as boolean | null
  }
  for (const key of ['errno', 'httpStatus', 'elapsedMs'] as const) {
    const item = input[key]
    if (
      item !== undefined &&
      item !== null &&
      (typeof item !== 'number' ||
        !Number.isInteger(item) ||
        (key === 'errno'
          ? item < -2147483648 || item > 2147483647
          : key === 'httpStatus'
            ? item < 100 || item > 599
            : item < 0 || item > 1800000))
    )
      return null
    if (item !== undefined) record[key] = item as number | null
  }
  if (
    input.closeReason !== undefined &&
    input.closeReason !== null &&
    !reasons.includes(input.closeReason as (typeof reasons)[number])
  )
    return null
  if (input.closeReason !== undefined)
    record.closeReason = input.closeReason as LoginDiagnostic['closeReason']
  // Unrecognized native codes are not reflected into the production file.
  record.errorCode = isSafeLoginDiagnosticCode(input.errorCode)
    ? input.errorCode
    : null
  return record
}

export function rendererLoginDiagnostic(
  message: string,
  isMainFrame: boolean,
  trustedOrigin: boolean,
): LoginDiagnostic | null {
  if (
    !isMainFrame ||
    !trustedOrigin ||
    message.length > 2048 ||
    !message.startsWith(rendererLoginDiagnosticPrefix)
  )
    return null
  try {
    const record = safeLoginDiagnostic(
      JSON.parse(message.slice(rendererLoginDiagnosticPrefix.length)),
    )
    if (
      !record ||
      record.source !== 'renderer' ||
      !['entry', 'focus', 'lease', 'open', 'cleanup'].includes(record.phase)
    )
      return null
    return record
  } catch {
    return null
  }
}

export function installRendererLoginDiagnostics(
  contents: WebContents,
  trustedOrigin: string,
  receive: (record: LoginDiagnostic) => void,
): void {
  contents.on('console-message', (details) => {
    try {
      if (contents.isDestroyed()) return
      const record = rendererLoginDiagnostic(
        details.message,
        details.frame === contents.mainFrame,
        isTrustedRendererUrl(details.frame.url, trustedOrigin) &&
          isTrustedRendererUrl(contents.getURL(), trustedOrigin),
      )
      if (record) receive(record)
    } catch {
      /* Never print a source URL or raw console payload. */
    }
  })
}

export class LoginDiagnosticFile {
  private pending = Promise.resolve()
  private queued = 0
  readonly filePath: string
  constructor(
    userData: string,
    private readonly maxBytes = 512 * 1024,
  ) {
    this.filePath = path.join(userData, 'diagnostics', 'shop-login.jsonl')
  }
  write(value: unknown): void {
    const safe = safeLoginDiagnostic(value)
    if (!safe || this.queued >= 128) return
    const line = JSON.stringify(safe) + '\n'
    this.queued++
    this.pending = this.pending
      .then(async () => {
        await mkdir(path.dirname(this.filePath), {
          recursive: true,
          mode: 0o700,
        })
        const size = await stat(this.filePath)
          .then((item) => item.size)
          .catch(() => 0)
        if (size + Buffer.byteLength(line) > this.maxBytes) {
          await rm(this.filePath + '.1', { force: true })
          await rename(this.filePath, this.filePath + '.1').catch(
            (error: unknown) => {
              if (
                !error ||
                typeof error !== 'object' ||
                (error as { code?: unknown }).code !== 'ENOENT'
              )
                throw error
            },
          )
        }
        await appendFile(this.filePath, line, {
          encoding: 'utf8',
          mode: 0o600,
        })
      })
      .catch(() => {
        // Do not persist or print raw file errors. Logging cannot change login.
      })
      .finally(() => {
        this.queued--
      })
  }
  flush(): Promise<void> {
    return this.pending
  }
}

export function createLoginDiagnosticRecorder(
  sink: Pick<LoginDiagnosticFile, 'write'>,
  isPackaged: boolean,
  developmentConsole: (record: LoginDiagnostic) => void = () => undefined,
): (record: LoginDiagnostic) => void {
  return (value) => {
    try {
      const safe = safeLoginDiagnostic(value)
      if (!safe) return
      sink.write(safe)
      if (!isPackaged) developmentConsole(safe)
    } catch {
      /* This observer is never a prerequisite for login. */
    }
  }
}
