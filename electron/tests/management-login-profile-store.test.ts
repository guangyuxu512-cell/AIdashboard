import assert from 'node:assert/strict'
import test from 'node:test'

import { ManagementLoginService } from '../services/management-login-service'
import {
  ManagementLoginProfileStore,
  type ManagementLoginProfileFileSystem,
  type ManagementLoginProfileMappingStore,
} from '../services/management-login-profile'

const filePath = 'profiles.json'
const teamId = '00000000-0000-4000-8000-000000000004'
const shopA = '00000000-0000-4000-8000-000000000011'
const shopB = '00000000-0000-4000-8000-000000000012'
const attemptA = '00000000-0000-4000-8000-000000000001'
const attemptB = '00000000-0000-4000-8000-000000000002'
const partitionA = `persist:management-login-${attemptA}`
const partitionB = `persist:management-login-${attemptB}`

class MemoryFileSystem implements ManagementLoginProfileFileSystem {
  readonly files = new Map<string, string>()
  readFailure: Error | null = null
  writeFailure: Error | null = null
  renameFailure: Error | null = null

  async readFile(path: string, _encoding: 'utf8'): Promise<string> {
    if (this.readFailure) throw this.readFailure
    const contents = this.files.get(path)
    if (contents === undefined) throw fileError('ENOENT')
    return contents
  }

  async writeFile(
    path: string,
    contents: string,
    _encoding: 'utf8',
  ): Promise<void> {
    if (this.writeFailure) throw this.writeFailure
    this.files.set(path, contents)
  }

  async rename(sourcePath: string, destinationPath: string): Promise<void> {
    if (this.renameFailure) throw this.renameFailure
    const contents = this.files.get(sourcePath)
    if (contents === undefined) throw fileError('ENOENT')
    this.files.set(destinationPath, contents)
    this.files.delete(sourcePath)
  }
}

test('profile store only treats a missing file as first initialization', async () => {
  const fileSystem = new MemoryFileSystem()
  const store = createStore(fileSystem)

  assert.equal(await store.load(shopA, 'douyin'), null)
  await store.save(shopA, 'douyin', partitionA)

  assert.deepEqual(await store.load(shopA, 'douyin'), {
    platform: 'douyin',
    partition: partitionA,
    updatedAt: '2026-09-13T00:00:00.000Z',
  })
})

test('profile store preserves mappings for other shops and supports normal recovery', async () => {
  const fileSystem = new MemoryFileSystem()
  fileSystem.files.set(
    filePath,
    JSON.stringify({
      [shopA]: {
        platform: 'douyin',
        partition: partitionA,
        updatedAt: '2026-08-01T00:00:00.000Z',
      },
    }),
  )
  const store = createStore(fileSystem)

  await store.save(shopB, 'pdd', partitionB)

  assert.deepEqual(await store.load(shopA, 'douyin'), {
    platform: 'douyin',
    partition: partitionA,
    updatedAt: '2026-08-01T00:00:00.000Z',
  })
  assert.deepEqual(await store.load(shopB, 'pdd'), {
    platform: 'pdd',
    partition: partitionB,
    updatedAt: '2026-09-13T00:00:00.000Z',
  })
  assert.equal(await store.load(shopA, 'pdd'), null)
})

test('profile store keeps the original file when JSON or structure is invalid', async () => {
  for (const original of [
    '{broken json',
    JSON.stringify({ [shopA]: { platform: 'unregistered' } }),
    JSON.stringify([]),
  ]) {
    const fileSystem = new MemoryFileSystem()
    fileSystem.files.set(filePath, original)
    const store = createStore(fileSystem)

    await assert.rejects(store.load(shopA, 'douyin'), /已保留原文件/)
    await assert.rejects(store.save(shopB, 'pdd', partitionB), /已保留原文件/)
    assert.equal(fileSystem.files.get(filePath), original)
  }
})

test('profile store reports read permission failures without treating them as empty', async () => {
  const fileSystem = new MemoryFileSystem()
  fileSystem.files.set(filePath, '{"existing":"unchanged"}')
  fileSystem.readFailure = fileError('EACCES')
  const store = createStore(fileSystem)

  await assert.rejects(store.load(shopA, 'douyin'), /没有文件访问权限/)
  await assert.rejects(
    store.save(shopA, 'douyin', partitionA),
    /没有文件访问权限/,
  )
  assert.equal(fileSystem.files.get(filePath), '{"existing":"unchanged"}')
})

test('profile store preserves the original mapping when atomic write or replace fails', async () => {
  for (const failure of ['write', 'rename'] as const) {
    const fileSystem = new MemoryFileSystem()
    const original = JSON.stringify({
      [shopA]: {
        platform: 'douyin',
        partition: partitionA,
        updatedAt: '2026-08-01T00:00:00.000Z',
      },
    })
    fileSystem.files.set(filePath, original)
    if (failure === 'write') fileSystem.writeFailure = fileError('ENOSPC')
    else fileSystem.renameFailure = fileError('EPERM')
    const store = createStore(fileSystem)

    await assert.rejects(store.save(shopB, 'pdd', partitionB), /原文件未被覆盖/)
    assert.equal(fileSystem.files.get(filePath), original)
    assert.deepEqual(
      await readOriginalMapping(fileSystem),
      JSON.parse(original),
    )
  }
})

test('profile store serializes concurrent read-modify-write operations', async () => {
  const fileSystem = new MemoryFileSystem()
  const store = createStore(fileSystem)

  await Promise.all([
    store.save(shopA, 'douyin', partitionA),
    store.save(shopB, 'pdd', partitionB),
  ])

  const persisted = JSON.parse(
    fileSystem.files.get(filePath) ?? '{}',
  ) as Record<string, { partition: string }>
  assert.equal(persisted[shopA]?.partition, partitionA)
  assert.equal(persisted[shopB]?.partition, partitionB)
})

test('server success remains completed when local profile persistence fails', async () => {
  const failingStore: ManagementLoginProfileMappingStore = {
    load: async () => null,
    save: async () => {
      throw new Error('磁盘空间不足')
    },
  }
  const requests: string[] = []

  await withMockedFetch(
    async (input) => {
      const url = String(input)
      requests.push(url)
      if (url.includes('/session/refresh')) {
        return jsonResponse({
          shop_id: shopA,
          status: 'valid',
          version: 3,
          validated_at: '2026-09-13T00:01:00.000Z',
          cookie_updates_applied: 0,
          used_cached_validation: false,
        })
      }
      return jsonResponse({
        shop: {
          shop_id: shopA,
          platform_shop_id: 'platform-shop-a',
          display_name: '店铺 A',
        },
        credential: { masked_identifier: '138****8888' },
        session: {
          status: 'captured',
          version: 1,
          captured_at: '2026-09-13T00:00:00.000Z',
        },
      })
    },
    async () => {
      const completeService = new ManagementLoginService({
        backendBaseUrl: 'http://127.0.0.1:8000/',
        profileMappingStore: failingStore,
      })
      const completePayload = seedAttempt(completeService, attemptA)

      const completed = await completeService.complete({
        attemptId: attemptA,
        loginIdentifier: 'account@example.com',
        secret: 'secret',
        preferredVerificationChannel: 'manual',
      })

      assert.match(
        completed.profileMappingWarning ?? '',
        /服务器已完成店铺接入/,
      )
      assert.equal(attemptsOf(completeService).has(attemptA), false)
      assert.equal(
        completePayload.every((byte) => byte === 0),
        true,
      )
      await assert.rejects(
        completeService.complete({
          attemptId: attemptA,
          loginIdentifier: 'account@example.com',
          secret: 'secret',
          preferredVerificationChannel: 'manual',
        }),
        /登录尝试不存在/,
      )

      const refreshService = new ManagementLoginService({
        backendBaseUrl: 'http://127.0.0.1:8000/',
        profileMappingStore: failingStore,
      })
      seedAttempt(refreshService, attemptB, {
        shopId: shopA,
        leaseId: '00000000-0000-4000-8000-000000000021',
        expectedVersion: 2,
      })

      const refreshed = await refreshService.refresh(attemptB)

      assert.match(
        refreshed.profileMappingWarning ?? '',
        /服务器已恢复并验证登录会话/,
      )
      assert.equal(attemptsOf(refreshService).has(attemptB), false)
    },
  )

  assert.equal(requests.length, 2)
})

test('business request failures remain failures and do not attempt local persistence', async () => {
  let saveCalls = 0
  const store: ManagementLoginProfileMappingStore = {
    load: async () => null,
    save: async () => {
      saveCalls += 1
    },
  }
  const service = new ManagementLoginService({
    backendBaseUrl: 'http://127.0.0.1:8000/',
    profileMappingStore: store,
  })
  seedAttempt(service, attemptA)

  await withMockedFetch(
    async () => jsonResponse({ message: '服务器拒绝接入' }, 409),
    async () => {
      await assert.rejects(
        service.complete({
          attemptId: attemptA,
          loginIdentifier: 'account@example.com',
          secret: 'secret',
          preferredVerificationChannel: 'manual',
        }),
        /服务器拒绝接入/,
      )
    },
  )

  assert.equal(saveCalls, 0)
  assert.equal(attemptsOf(service).has(attemptA), true)
})

function createStore(
  fileSystem: ManagementLoginProfileFileSystem,
): ManagementLoginProfileStore {
  return new ManagementLoginProfileStore(
    () => filePath,
    fileSystem,
    () => new Date('2026-09-13T00:00:00.000Z'),
  )
}

async function readOriginalMapping(
  fileSystem: MemoryFileSystem,
): Promise<unknown> {
  return JSON.parse(await fileSystem.readFile(filePath, 'utf8'))
}

function fileError(code: string): Error & { code: string } {
  return Object.assign(new Error(code), { code })
}

function attemptsOf(service: ManagementLoginService): Map<string, unknown> {
  return (service as unknown as { attempts: Map<string, unknown> }).attempts
}

function seedAttempt(
  service: ManagementLoginService,
  attemptId: string,
  recovery: {
    shopId: string
    leaseId: string
    expectedVersion: number
  } | null = null,
): Buffer {
  const payload = Buffer.from('captured-session')
  attemptsOf(service).set(attemptId, {
    attemptId,
    platform: 'douyin',
    teamId,
    appSession: {
      cookies: {
        get: async () => [
          { name: 'siyu_human_session', value: 'human-session-token' },
        ],
      },
    },
    partition: `persist:management-login-${attemptId}`,
    window: null,
    status: 'identified',
    identity: {
      platform: 'douyin',
      platformShopId: 'platform-shop-a',
      shopDisplayName: '店铺 A',
    },
    capturedSession: {
      payload,
      capturedAt: '2026-09-13T00:00:00.000Z',
      cookieCount: 2,
    },
    message: '已识别',
    systemCloseRequested: false,
    expiresAt: null,
    recovery,
    profileReused: false,
    lastPddVerificationFailureFingerprint: null,
    lastPddVerificationFailureAt: null,
  })
  return payload
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

async function withMockedFetch<T>(
  implementation: (input: RequestInfo | URL) => Promise<Response>,
  operation: () => Promise<T>,
): Promise<T> {
  const fetchTarget = globalThis as typeof globalThis & {
    fetch: typeof globalThis.fetch
  }
  const originalFetch = fetchTarget.fetch
  fetchTarget.fetch = async (input) => implementation(input)
  try {
    return await operation()
  } finally {
    fetchTarget.fetch = originalFetch
  }
}
