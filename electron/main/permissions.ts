import type { WebContents } from 'electron'

import { isTrustedRendererUrl } from '../config/runtime'

export const clipboardSanitizedWritePermission = 'clipboard-sanitized-write'

interface PermissionSource {
  getURL(): string
}

interface ClipboardWritePermissionInput {
  mainWebContents: PermissionSource
  requestingWebContents: PermissionSource | null
  permission: string
  requestingUrl: string
  isMainFrame: boolean
  trustedRendererOrigin: string
}

export function isTrustedMainWindowClipboardWritePermission(
  input: ClipboardWritePermissionInput,
): boolean {
  return (
    input.permission === clipboardSanitizedWritePermission &&
    input.requestingWebContents === input.mainWebContents &&
    input.isMainFrame &&
    isTrustedRendererUrl(
      input.mainWebContents.getURL(),
      input.trustedRendererOrigin,
    ) &&
    isTrustedRendererUrl(input.requestingUrl, input.trustedRendererOrigin)
  )
}

export function installMainWindowPermissionHandlers(
  mainWebContents: WebContents,
  trustedRendererOrigin: string,
): void {
  const allowsClipboardWrite = (
    requestingWebContents: PermissionSource | null,
    permission: string,
    requestingUrl: string,
    isMainFrame: boolean,
  ): boolean =>
    isTrustedMainWindowClipboardWritePermission({
      mainWebContents,
      requestingWebContents,
      permission,
      requestingUrl,
      isMainFrame,
      trustedRendererOrigin,
    })

  mainWebContents.session.setPermissionCheckHandler(
    (requestingWebContents, permission, requestingOrigin, details) =>
      allowsClipboardWrite(
        requestingWebContents,
        permission,
        details.requestingUrl ?? requestingOrigin,
        details.isMainFrame,
      ),
  )
  mainWebContents.session.setPermissionRequestHandler(
    (requestingWebContents, permission, callback, details) => {
      callback(
        allowsClipboardWrite(
          requestingWebContents,
          permission,
          details.requestingUrl,
          details.isMainFrame,
        ),
      )
    },
  )
}
