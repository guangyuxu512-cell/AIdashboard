import assert from 'node:assert/strict'
import path from 'node:path'
import test from 'node:test'

import {
  isTrustedRendererUrl,
  productionConsoleOrigin,
  productionConsoleUrl,
  resolveDesktopRuntimeConfig,
  resolveDesktopUserDataPath,
} from '../config/runtime'

test('packaged Desktop always uses the fixed same-site production origin', () => {
  assert.deepEqual(
    resolveDesktopRuntimeConfig({
      isPackaged: true,
      environment: {
        FRONTEND_DEV_SERVER_URL: 'https://untrusted.example/',
        CONTROL_CENTER_BACKEND_URL: 'https://untrusted.example/',
      },
    }),
    {
      rendererUrl: productionConsoleUrl,
      rendererOrigin: productionConsoleOrigin,
      backendBaseUrl: productionConsoleUrl,
    },
  )
})

test('development only accepts registered loopback renderer ports', () => {
  assert.deepEqual(
    resolveDesktopRuntimeConfig({
      isPackaged: false,
      environment: {
        FRONTEND_DEV_SERVER_URL: 'http://127.0.0.1:5180/',
        CONTROL_CENTER_BACKEND_URL: 'http://localhost:8100/',
      },
    }),
    {
      rendererUrl: 'http://127.0.0.1:5180/',
      rendererOrigin: 'http://127.0.0.1:5180',
      backendBaseUrl: 'http://localhost:8100/',
    },
  )
  assert.throws(
    () =>
      resolveDesktopRuntimeConfig({
        isPackaged: false,
        environment: {
          FRONTEND_DEV_SERVER_URL: 'https://untrusted.example/',
        },
      }),
    /已登记的本机端口/,
  )
})

test('trusted renderer checks exact origin and rejects credentials or lookalikes', () => {
  assert.equal(
    isTrustedRendererUrl(
      'https://119.29.188.118/login#/shops',
      productionConsoleOrigin,
    ),
    true,
  )
  assert.equal(
    isTrustedRendererUrl(
      'https://119.29.188.118.attacker.example/',
      productionConsoleOrigin,
    ),
    false,
  )
  assert.equal(
    isTrustedRendererUrl(
      'https://user@119.29.188.118/',
      productionConsoleOrigin,
    ),
    false,
  )
  assert.equal(
    isTrustedRendererUrl('javascript:alert(1)', productionConsoleOrigin),
    false,
  )
})

test('Desktop userData path remains stable across application versions', () => {
  const appDataPath = path.resolve('C:\\Users\\tester\\AppData\\Roaming')
  assert.equal(
    resolveDesktopUserDataPath(appDataPath),
    path.join(appDataPath, 'Siyu AI Control Center'),
  )
  assert.throws(() => resolveDesktopUserDataPath('relative'))
})
