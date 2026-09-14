import assert from 'node:assert/strict'
import test from 'node:test'

import {
  clipboardSanitizedWritePermission,
  isTrustedMainWindowClipboardWritePermission,
} from '../main/permissions'

const trustedRendererOrigin = 'http://127.0.0.1:5180'

function source(url: string) {
  return { getURL: () => url }
}

test('trusted main renderer may request sanitized clipboard write', () => {
  const mainWebContents = source('http://127.0.0.1:5180/devices')

  assert.equal(
    isTrustedMainWindowClipboardWritePermission({
      mainWebContents,
      requestingWebContents: mainWebContents,
      permission: clipboardSanitizedWritePermission,
      requestingUrl: 'http://127.0.0.1:5180/devices',
      isMainFrame: true,
      trustedRendererOrigin,
    }),
    true,
  )
})

test('main permission policy rejects clipboard read and untrusted request contexts', () => {
  const trustedMain = source('http://127.0.0.1:5180/devices')
  const untrustedContents = source('https://attacker.example/')
  const cases = [
    {
      label: 'clipboard read',
      requestingWebContents: trustedMain,
      permission: 'clipboard-read',
      requestingUrl: 'http://127.0.0.1:5180/devices',
      isMainFrame: true,
      mainWebContents: trustedMain,
    },
    {
      label: 'other web contents',
      requestingWebContents: untrustedContents,
      permission: clipboardSanitizedWritePermission,
      requestingUrl: 'http://127.0.0.1:5180/devices',
      isMainFrame: true,
      mainWebContents: trustedMain,
    },
    {
      label: 'sub frame',
      requestingWebContents: trustedMain,
      permission: clipboardSanitizedWritePermission,
      requestingUrl: 'http://127.0.0.1:5180/devices',
      isMainFrame: false,
      mainWebContents: trustedMain,
    },
    {
      label: 'untrusted request URL',
      requestingWebContents: trustedMain,
      permission: clipboardSanitizedWritePermission,
      requestingUrl: 'https://attacker.example/',
      isMainFrame: true,
      mainWebContents: trustedMain,
    },
    {
      label: 'navigated main window',
      requestingWebContents: untrustedContents,
      permission: clipboardSanitizedWritePermission,
      requestingUrl: 'https://attacker.example/',
      isMainFrame: true,
      mainWebContents: untrustedContents,
    },
  ]

  for (const scenario of cases) {
    assert.equal(
      isTrustedMainWindowClipboardWritePermission({
        ...scenario,
        trustedRendererOrigin,
      }),
      false,
      scenario.label,
    )
  }
})
