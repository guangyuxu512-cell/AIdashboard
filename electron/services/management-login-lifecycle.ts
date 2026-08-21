import type { ManagementLoginStatus } from '../types'

export interface ManagementLoginWindowCloseContext {
  status: ManagementLoginStatus
  systemCloseRequested: boolean
  sessionCaptured: boolean
}

/**
 * Only Main's close request after a successful in-memory capture may preserve
 * the identified attempt. Every other window close is treated as an abort.
 */
export function shouldPreserveCapturedLogin(
  context: ManagementLoginWindowCloseContext,
): boolean {
  return (
    context.status === 'identified' &&
    context.systemCloseRequested &&
    context.sessionCaptured
  )
}
