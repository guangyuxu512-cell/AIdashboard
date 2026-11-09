import assert from 'node:assert/strict'
import test from 'node:test'
import vm from 'node:vm'
import path from 'node:path'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import type { Session } from 'electron'
import type { DouyinPlatformAuthAdapter } from '../services/douyin-platform-auth-adapter'

function adapter(
  fetch: (...args: unknown[]) => Promise<unknown>,
  location = { protocol: 'https:', hostname: 'fxg.jinritemai.com' },
) {
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
    executeJavaScript: () => { throw new Error('WebContents execution must not be used') },
    mainFrame: {
      executeJavaScript: (script: string) => vm.runInNewContext(script, {
        fetch, URL, Date, location: { ...location, origin: `${location.protocol}//${location.hostname}` }, AbortSignal,
        window: { localStorage: emptyStorage, sessionStorage: emptyStorage },
      }),
    },
  }
  vm.runInNewContext(readFileSync(sourcePath, 'utf8'), {
    exports,
    Buffer,
    require: (name: string) =>
      name === 'electron'
        ? { webContents: { fromId: () => contents } }
        : resolve(name),
  })
  return new exports.DouyinPlatformAuthAdapter!()
}
const emptyStorage = { length: 0, key: () => null, getItem: () => null }

test('merchant identity probe uses only the fixed same-origin endpoint and requires an exact ID', async () => {
  const paths: unknown[] = []
  const client = adapter(async (path) => {
    paths.push(path)
    return { ok: true, json: async () => ({ code: 0, data: { id: 'shop-a' } }) }
  })
  const result = await client.detectMerchantIdentity(42)
  assert.equal(result.status, 'confirmed')
  assert.equal(result.platformShopId, 'shop-a')
  assert.deepEqual(paths, ['/common/index/index'])
})

test('unknown merchant code and unsafe numeric identity never become a confirmed shop', async () => {
  for (const body of [
    { code: 10008, data: {} },
    { code: 0, data: { id: 9223372036854776000 } },
    { code: '0', data: { id: 'shop-a' } },
  ]) {
    const client = adapter(async () => ({ ok: true, json: async () => body }))
    assert.equal((await client.detectMerchantIdentity(42)).status, 'unverified')
  }
})

test('merchant identity never probes from an unrelated origin', async () => {
  let requests = 0
  const client = adapter(async () => { requests++; throw new Error('unexpected') },
    { protocol: 'https:', hostname: 'example.invalid' })
  assert.equal((await client.detectMerchantIdentity(42)).status, 'unverified')
  assert.equal(requests, 0)
})
const loginSession = {
  cookies: {
    get: async () => [
      { name: 'synthetic', value: 'synthetic', domain: '.jinritemai.com' },
    ],
  },
} as unknown as Session

test('session capture uses the main-frame fixed script and preserves its origin storage', async () => {
  const client = adapter(async () => { throw new Error('unexpected request') })
  const captured = await client.captureSession(loginSession, 42, {
    platform: 'douyin', platformShopId: 'shop-a', shopDisplayName: 'fixture',
  })
  const payload = JSON.parse(captured.payload.toString('utf8')) as { cookies: unknown[]; storage: { origin: string } }
  assert.equal(payload.cookies.length, 1)
  assert.equal(payload.storage.origin, 'https://fxg.jinritemai.com')
  captured.payload.fill(0)
})

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
  assert.equal(result.requestFailed, true)
  assert.equal(result.probes?.[0]?.httpStatus, null)
  assert.equal(result.probes?.[0]?.requestFailed, true)
  assert.ok(!JSON.stringify(result.probes).includes('private-'))
  assert.ok(!JSON.stringify(result.probes).includes('cors'))
})

test('a temporary HTTP service error is a failed request while an unauthenticated page may keep waiting', async () => {
  for (const [status, failed] of [[503, true], [429, true], [401, false], [403, false]] as const) {
    const client = adapter(async () => ({ status, text: async () => '{}' }))
    const result = await client.detectLoginStatus(loginSession, 42)
    assert.equal(result.readyForCapture, false)
    assert.equal(result.requestFailed, failed)
  }
})

for (const [scenario, body, status] of [
  [
    'account metadata is not shop identity',
    {
      data: {
        account_id: 'synthetic-account',
        account_name: 'Synthetic operator',
      },
    },
    200,
  ],
  [
    'nested account before shop is not a verified data.shop contract',
    {
      data: {
        account_info: {
          account_id: 'synthetic-account',
          account_name: 'Synthetic operator',
        },
        shop_info: { shop_id: 'synthetic-shop', shop_name: 'Synthetic shop' },
      },
    },
    200,
  ],
  [
    'an array never selects its first shop',
    {
      data: [
        { shop_id: 'synthetic-other', shop_name: 'Other' },
        { shop_id: 'synthetic-shop', shop_name: 'Target' },
      ],
    },
    200,
  ],
  [
    'business rejection is not identity success',
    {
      st: 12345,
      data: { shop_id: 'synthetic-shop', shop_name: 'Synthetic shop' },
    },
    200,
  ],
  [
    'HTTP rejection is not identity success',
    { st: 0, data: { shop_id: 'synthetic-shop', shop_name: 'Synthetic shop' } },
    401,
  ],
  [
    'unknown object fields are not stringified into identity',
    { data: { shop_id: {}, shop_name: 'Synthetic shop' } },
    200,
  ],
] as const) {
  test(scenario, async () => {
    let requests = 0
    const client = adapter(async (url) => {
      requests++
      assert.equal(
        url,
        'https://compass.jinritemai.com/compass_api/shop/mall/common/shop_info_v2',
      )
      return { status, text: async () => JSON.stringify(body) }
    })
    const result = await client.detectLoginStatus(loginSession, 42)
    assert.equal(result.identity, null)
    assert.equal(result.readyForCapture, false)
    assert.equal(result.pageContextAvailable, true)
    assert.equal(requests, 1)
    assert.equal(result.probes?.[0]?.probeIndex, 0)
    assert.equal(result.probes?.[0]?.httpStatus, status)
    assert.ok(!JSON.stringify(result.probes).includes('synthetic-'))
    await assert.rejects(
      client.captureSession(loginSession, 42, result.identity),
      /身份尚未识别/,
    )
    assert.equal(requests, 1)
  })
}

for (const st of [undefined, null, 0, '0']) {
  test(`verified v2 shop fields ignore unrelated account fields, st=${String(st)}`, async () => {
    let requests = 0
    const client = adapter(async () => {
      requests++
      return {
        status: 200,
        text: async () =>
          JSON.stringify({
            st,
            account_id: 'synthetic-person',
            account_name: 'Synthetic person',
            data: {
              shop_id: ' 9223372036854775807 ',
              shop_name: ' Synthetic shop ',
              account_id: 'synthetic-other',
            },
          }),
      }
    })
    const result = await client.detectLoginStatus(loginSession, 42)
    assert.equal(result.readyForCapture, true)
    assert.equal(result.identity?.platformShopId, '9223372036854775807')
    assert.equal(result.identity?.shopDisplayName, 'Synthetic shop')
    assert.equal(requests, 1)
    assert.equal(result.probes?.[0]?.probeIndex, 0)
  })
}

test('an unsafe numeric ID is not rounded into a different shop identity', async () => {
  const client = adapter(async () => ({
    status: 200,
    text: async () =>
      '{"st":0,"data":{"shop_id":9223372036854775807,"shop_name":"Synthetic shop"}}',
  }))
  const result = await client.detectLoginStatus(loginSession, 42)
  assert.equal(result.identity, null)
  assert.equal(result.readyForCapture, false)
})
