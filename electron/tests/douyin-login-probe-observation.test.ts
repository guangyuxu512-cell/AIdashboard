import assert from 'node:assert/strict'
import test from 'node:test'
import vm from 'node:vm'
import path from 'node:path'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import type { Session } from 'electron'
import type { DouyinPlatformAuthAdapter } from '../services/douyin-platform-auth-adapter'

function adapter(fetch: (...args: unknown[]) => Promise<unknown>) {
  const sourcePath = path.join(
    __dirname,
    '../services/douyin-platform-auth-adapter.js',
  )
  const resolve = createRequire(sourcePath)
  const exports: {
    DouyinPlatformAuthAdapter?: new () => DouyinPlatformAuthAdapter
  } = {}
  const contents = {
    isDestroyed: () => false,
    executeJavaScript: (script: string) =>
      vm.runInNewContext(script, { fetch, URL, Date }),
  }
  vm.runInNewContext(readFileSync(sourcePath, 'utf8'), {
    exports,
    require: (name: string) =>
      name === 'electron'
        ? { webContents: { fromId: () => contents } }
        : resolve(name),
  })
  return new exports.DouyinPlatformAuthAdapter!()
}
const loginSession = {
  cookies: {
    get: async () => [
      { name: 'synthetic', value: 'synthetic', domain: '.jinritemai.com' },
    ],
  },
} as unknown as Session

test('existing fixed probe records one successful request without adding requests or persisting identity in observations', async () => {
  let requests = 0
  const client = adapter(async () => {
    requests++
    return {
      status: 200,
      text: async () =>
        JSON.stringify({
          data: {
            shop_id: 'private-identity-fixture',
            shop_name: 'private-name-fixture',
          },
        }),
    }
  })
  const result = await client.detectLoginStatus(loginSession, 42)
  assert.equal(requests, 1)
  assert.equal(result.readyForCapture, true)
  assert.equal(result.pageContextAvailable, true)
  assert.equal(result.probes?.[0]?.httpStatus, 200)
  assert.equal(result.probes?.[0]?.probeIndex, 0)
  assert.ok(!JSON.stringify(result.probes).includes('private-'))
})
test('an existing failed fetch stops at the original point, records failure not CORS/auth expiry, and does not retry', async () => {
  let requests = 0
  const client = adapter(async () => {
    requests++
    throw new TypeError('private-message-fixture')
  })
  const result = await client.detectLoginStatus(loginSession, 42)
  assert.equal(requests, 1)
  assert.equal(result.readyForCapture, false)
  assert.equal(result.probes?.[0]?.httpStatus, null)
  assert.equal(result.probes?.[0]?.requestFailed, true)
  assert.ok(!JSON.stringify(result.probes).includes('private-'))
  assert.ok(!JSON.stringify(result.probes).includes('cors'))
})
