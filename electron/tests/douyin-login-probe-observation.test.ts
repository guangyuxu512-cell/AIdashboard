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
