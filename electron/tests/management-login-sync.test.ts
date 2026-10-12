import assert from 'node:assert/strict'
import test from 'node:test'
import { EventEmitter } from 'node:events'
import type { BrowserWindow, Session } from 'electron'
import {
  ManagementLoginService,
  type ManagementLoginDiagnostic,
} from '../services/management-login-service'
import type {
  ManagementLoginOpenInput,
  ManagementLoginStatusResult,
} from '../types'
import type {
  CapturedManagementSession,
  PlatformAuthAdapter,
  PlatformLoginDetectionResult,
} from '../services/platform-auth-adapter'
import type { ManagementLoginProfileMappingStore } from '../services/management-login-profile'

const shopId = 'd6ac091c-133e-40c4-a827-0951a2309f20'
const teamId = '4494316a-832b-465e-a20d-d748c173601d'
const input: ManagementLoginOpenInput = {
  platform: 'douyin',
  teamId,
  recovery: {
    shopId,
    leaseId: 'bcdd74b1-a41c-43ad-a274-09f8dffcf1f9',
    expectedVersion: 3,
  },
}
const loginSession = {
  cookies: {
    get: async () => [{ name: 'siyu_human_session', value: 'isolated-test' }],
  },
  setPermissionCheckHandler() {},
  setPermissionRequestHandler() {},
} as unknown as Session

class WindowStub extends EventEmitter {
  destroyed = false
  focused = 0
  loadFailure: Error | null = null
  loading = false
  webContents = Object.assign(new EventEmitter(), {
    id: 42,
    session: loginSession,
    setWindowOpenHandler() {},
    isDestroyed: () => this.destroyed,
    isLoadingMainFrame: () => this.loading,
  })
  isDestroyed() {
    return this.destroyed
  }
  isMinimized() {
    return false
  }
  restore() {}
  focus() {
    this.focused++
  }
  async loadURL() {
    if (this.loadFailure) throw this.loadFailure
  }
  close() {
    if (!this.destroyed) {
      this.destroyed = true
      this.emit('closed')
    }
  }
}

function setup(
  profileMappingStore?: ManagementLoginProfileMappingStore,
  failures?: {
    load?: Error
    detection?: Error
    capture?: Error
    onDiagnostic?: (record: ManagementLoginDiagnostic) => void
    metadataTimeoutMs?: number
    detectionResult?: PlatformLoginDetectionResult
  },
) {
  const windows: WindowStub[] = []
  const buffers: Buffer[] = []
  let captures = 0
  const adapter: PlatformAuthAdapter = {
    platformCode: 'douyin',
    loginUrl: 'https://test.example/login',
    loginWindowTitle: 'isolated test',
    async detectLoginStatus() {
      if (failures?.detection) throw failures.detection
      if (failures?.detectionResult) return failures.detectionResult
      return {
        readyForCapture: true,
        message: 'identified',
        identity: {
          platform: 'douyin',
          platformShopId: 'matching-test-shop',
          shopDisplayName: 'test shop',
        },
      }
    },
    async captureSession() {
      if (failures?.capture) throw failures.capture
      captures++
      const payload = Buffer.from('isolated-candidate')
      buffers.push(payload)
      return { payload, capturedAt: '2026-10-11T09:00:00Z', cookieCount: 1 }
    },
  }
  const service = new ManagementLoginService({
    adapters: new Map([['douyin', adapter]]),
    createWindow() {
      const window = new WindowStub()
      window.loadFailure = failures?.load ?? null
      windows.push(window)
      return window as unknown as BrowserWindow
    },
    fromPartition: () => loginSession,
    onDiagnostic: failures?.onDiagnostic,
    metadataTimeoutMs: failures?.metadataTimeoutMs,
    profileMappingStore: profileMappingStore ?? {
      async load() {
        return null
      },
      async save() {},
    },
  })
  return {
    service,
    adapter,
    windows,
    buffers,
    captures: () => captures,
    parent: new WindowStub() as unknown as BrowserWindow,
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((done, fail) => {
    resolve = done
    reject = fail
  })
  return { promise, resolve, reject }
}
const nextTurn = () => new Promise<void>((resolve) => setImmediate(resolve))

test('native close settles an unresolved single-flight detection after focus, releases once and ignores late identity', async () => {
  const originalFetch = globalThis.fetch
  const requests: string[] = []
  globalThis.fetch = async (_url, init) => {
    requests.push(init?.method ?? 'GET')
    return new Response(null, { status: 204 })
  }
  const state = setup()
  const detecting = deferred<PlatformLoginDetectionResult>()
  let detections = 0
  state.adapter.detectLoginStatus = () => {
    detections++
    return detecting.promise
  }
  try {
    const opened = await state.service.open(state.parent, {
      ...input,
      teamId: undefined,
    })
    const settled: ManagementLoginStatusResult[] = []
    const polling = state.service.getStatus(opened.attemptId).then((status) => {
      settled.push(status)
      return status
    })
    const duplicate = state.service.getStatus(opened.attemptId)
    assert.equal(
      await state.service.focusShop(state.parent, {
        shopId,
        platform: 'douyin',
      }),
      true,
    )
    state.windows[0]!.close()
    await nextTurn()
    // Detection deliberately remains unresolved: another poll cannot rescue
    // the Renderer while its first IPC is still awaiting page execution.
    assert.equal(settled[0]?.status, 'closed')
    assert.deepEqual(await duplicate, await polling)
    assert.equal(detections, 1)
    assert.equal(state.windows.length, 1)
    assert.equal(
      (await state.service.getStatus(opened.attemptId)).status,
      'closed',
    )
    detecting.resolve({
      readyForCapture: true,
      message: 'late identity',
      identity: {
        platform: 'douyin',
        platformShopId: 'matching-test-shop',
        shopDisplayName: 'test shop',
      },
    })
    await nextTurn()
    const closed = await state.service.getStatus(opened.attemptId)
    assert.equal(closed.status, 'closed')
    assert.equal(closed.identity, null)
    assert.equal(closed.sessionCaptured, false)
    assert.equal(state.captures(), 0)
    await assert.rejects(state.service.refresh(opened.attemptId))
    await state.service.close(opened.attemptId)
    assert.equal(requests.filter((method) => method === 'DELETE').length, 1)
    assert.equal(requests.filter((method) => method === 'POST').length, 0)
  } finally {
    detecting.resolve({
      identity: null,
      readyForCapture: false,
      message: 'waiting',
    })
    await state.service.closeAll()
    globalThis.fetch = originalFetch
  }
})

test('explicit cancellation settles unresolved status and a late detection rejection cannot revive it', async () => {
  const originalFetch = globalThis.fetch
  let releases = 0
  globalThis.fetch = async (_url, init) => {
    if (init?.method === 'DELETE') releases++
    assert.notEqual(init?.method, 'POST')
    return new Response(null, { status: 204 })
  }
  const state = setup()
  const detecting = deferred<PlatformLoginDetectionResult>()
  state.adapter.detectLoginStatus = () => detecting.promise
  try {
    const opened = await state.service.open(state.parent, input)
    const settled: ManagementLoginStatusResult[] = []
    const polling = state.service.getStatus(opened.attemptId).then((status) => {
      settled.push(status)
      return status
    })
    await state.service.close(opened.attemptId)
    await nextTurn()
    assert.equal(settled[0]?.status, 'closed')
    assert.equal((await polling).sessionCaptured, false)
    detecting.reject(new Error('isolated late detection failure'))
    await nextTurn()
    await assert.rejects(state.service.getStatus(opened.attemptId), /不存在/)
    await state.service.close(opened.attemptId)
    assert.equal(releases, 1)
    assert.equal(state.captures(), 0)
  } finally {
    detecting.resolve({
      identity: null,
      readyForCapture: false,
      message: 'waiting',
    })
    await state.service.closeAll()
    globalThis.fetch = originalFetch
  }
})

test('native close settles pending capture, erases its late payload and never saves or maps it', async () => {
  const originalFetch = globalThis.fetch
  const methods: string[] = []
  globalThis.fetch = async (_url, init) => {
    methods.push(init?.method ?? 'GET')
    return new Response(null, { status: 204 })
  }
  let profileSaves = 0
  const state = setup({
    async load() {
      return null
    },
    async save() {
      profileSaves++
    },
  })
  const capturing = deferred<CapturedManagementSession>()
  let captureCalls = 0
  state.adapter.captureSession = () => {
    captureCalls++
    return capturing.promise
  }
  const payload = Buffer.from('isolated-late-candidate')
  const captured = {
    payload,
    capturedAt: '2026-10-11T09:00:00Z',
    cookieCount: 1,
  }
  try {
    const opened = await state.service.open(state.parent, input)
    const settled: ManagementLoginStatusResult[] = []
    const polling = state.service.getStatus(opened.attemptId).then((status) => {
      settled.push(status)
      return status
    })
    await nextTurn()
    assert.equal(captureCalls, 1)
    state.windows[0]!.close()
    await nextTurn()
    assert.equal(settled[0]?.status, 'closed')
    await polling
    capturing.resolve(captured)
    await nextTurn()
    assert.ok(payload.every((value) => value === 0))
    const closed = await state.service.getStatus(opened.attemptId)
    assert.equal(closed.status, 'closed')
    assert.equal(closed.identity, null)
    assert.equal(closed.sessionCaptured, false)
    await assert.rejects(state.service.refresh(opened.attemptId))
    await state.service.close(opened.attemptId)
    assert.equal(profileSaves, 0)
    assert.deepEqual(methods, ['DELETE'])
  } finally {
    capturing.resolve(captured)
    await state.service.closeAll()
    globalThis.fetch = originalFetch
  }
})

test('unknown attempts reject instead of returning a fabricated closed or null status', async () => {
  const state = setup()
  await assert.rejects(state.service.getStatus('unknown-attempt'), /不存在/)
  assert.equal(state.windows.length, 0)
  assert.equal(state.captures(), 0)
})

test('existing-shop super context without a team omits the header on metadata/save/release and preserves single capture/CAS/retained focus', async () => {
  const originalFetch = globalThis.fetch
  const calls: Array<{ method: string; team: string | null }> = []
  globalThis.fetch = async (_url, init) => {
    calls.push({
      method: init?.method ?? 'GET',
      team: new Headers(init?.headers).get('x-team-id'),
    })
    assert.ok(new Headers(init?.headers).has('cookie'))
    return Response.json({
      shop_id: shopId,
      status: 'valid',
      version: 4,
      validated_at: '2026-10-11T09:00:01Z',
      used_cached_validation: false,
    })
  }
  const state = setup()
  try {
    const globalInput = { ...input, teamId: undefined }
    assert.equal(
      await state.service.focusShop(state.parent, {
        shopId,
        platform: 'douyin',
      }),
      false,
    )
    const opened = await state.service.open(state.parent, globalInput)
    await state.service.getStatus(opened.attemptId)
    await state.service.refresh(opened.attemptId)
    assert.equal(state.windows[0]!.destroyed, false)
    assert.equal(
      await state.service.focusShop(state.parent, {
        shopId,
        platform: 'douyin',
      }),
      true,
    )
    assert.equal(state.captures(), 1)
    state.windows[0]!.close()
    const cancelled = await state.service.open(state.parent, globalInput)
    await state.service.close(cancelled.attemptId)
    assert.ok(calls.some((call) => call.method === 'DELETE'))
    assert.equal(calls.filter((call) => call.method === 'POST').length, 1)
    assert.ok(calls.every((call) => call.team === null))
  } finally {
    await state.service.closeAll()
    globalThis.fetch = originalFetch
  }
})

test('unscoped metadata still rejects revoked personnel and non-super contexts before lease/open', async () => {
  const originalFetch = globalThis.fetch
  const state = setup()
  try {
    for (const status of [401, 403]) {
      globalThis.fetch = async () =>
        Response.json({ private: 'ignored fixture' }, { status })
      await assert.rejects(
        state.service.focusShop(state.parent, { shopId, platform: 'douyin' }),
        status === 401 ? /SHOP_LOGIN_AUTH_REQUIRED/ : /SHOP_LOGIN_FORBIDDEN/,
      )
    }
    assert.equal(state.windows.length, 0)
    assert.equal(state.captures(), 0)
  } finally {
    await state.service.closeAll()
    globalThis.fetch = originalFetch
  }
})

test('same-window navigation/probe/script observation is bounded, redacted and detached without changing capture', async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => new Response(null, { status: 204 })
  const records: ManagementLoginDiagnostic[] = []
  const state = setup(undefined, {
    onDiagnostic: (record) => records.push(record),
    detectionResult: {
      identity: null,
      readyForCapture: false,
      pageContextAvailable: true,
      message: 'waiting',
      probes: [
        { probeIndex: 0, httpStatus: 200, elapsedMs: 13, requestFailed: false },
      ],
    },
  })
  try {
    const opened = await state.service.open(state.parent, input)
    const contents = state.windows[0]!.webContents
    contents.emit('did-start-navigation', {
      isMainFrame: true,
      url: 'https://compass.jinritemai.com/shop?private-fixture=do-not-log',
    })
    contents.emit(
      'did-navigate',
      {},
      'https://compass.jinritemai.com/shop?private-fixture=do-not-log',
      200,
      'secret ignored',
    )
    for (let i = 0; i < 25; i++)
      contents.emit('console-message', {
        level: 'error',
        message:
          'TypeError: private-fixture https://secret.invalid/?credential=private-fixture',
      })
    await state.service.getStatus(opened.attemptId)
    await state.service.getStatus(opened.attemptId)
    assert.equal(
      records.filter((record) => record.phase === 'account_probe').length,
      1,
    )
    assert.equal(
      records.filter((record) => record.phase === 'script').length,
      20,
    )
    assert.ok(
      records
        .filter((record) => record.phase === 'script')
        .every(
          (record) =>
            record.errorCode === 'JS_TYPE_ERROR' &&
            record.corsBlocked === false,
        ),
    )
    assert.ok(
      records.some(
        (record) =>
          record.phase === 'detect' &&
          record.captureReady === false &&
          record.identityPresent === false &&
          record.pageContextAvailable === true,
      ),
    )
    contents.emit('did-start-navigation', {
      isMainFrame: true,
      url: 'https://compass.jinritemai.com/shop?different-secret=ignored',
    })
    contents.emit('console-message', {
      level: 'error',
      message: 'Access has been blocked by CORS policy: private-fixture',
    })
    await state.service.getStatus(opened.attemptId)
    assert.equal(
      records.filter((record) => record.phase === 'account_probe').length,
      2,
    )
    assert.ok(
      records.some(
        (record) =>
          record.phase === 'script' &&
          record.navigationSequence === 2 &&
          record.corsBlocked === true &&
          record.scriptErrorCount === 1,
      ),
    )
    assert.equal(state.windows[0]!.destroyed, false)
    await state.service.close(opened.attemptId)
    const length = records.length
    contents.emit('console-message', {
      level: 'error',
      message: 'private-fixture',
    })
    contents.emit('did-start-navigation', {
      isMainFrame: true,
      url: 'https://secret.invalid',
    })
    assert.equal(records.length, length)
    assert.equal(contents.listenerCount('console-message'), 0)
    assert.equal(contents.listenerCount('did-navigate'), 0)
    assert.equal(state.captures(), 0)
    assert.equal(JSON.stringify(records).includes('private-fixture'), false)
    assert.equal(JSON.stringify(records).includes('secret.invalid'), false)
  } finally {
    await state.service.closeAll()
    globalThis.fetch = originalFetch
  }
})

test('optional observation getters and detach failures cannot fail capture polling or lease cleanup', async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => new Response(null, { status: 204 })
  const records: ManagementLoginDiagnostic[] = []
  const detection: PlatformLoginDetectionResult = {
    identity: null,
    readyForCapture: false,
    message: 'waiting',
    get probes(): PlatformLoginDetectionResult['probes'] {
      throw new Error('private optional observation getter')
    },
    get pageContextAvailable(): boolean | undefined {
      throw new Error('private optional page getter')
    },
  }
  const state = setup(undefined, {
    onDiagnostic: (record) => records.push(record),
    detectionResult: detection,
  })
  try {
    const opened = await state.service.open(state.parent, input)
    assert.equal(
      (await state.service.getStatus(opened.attemptId)).status,
      'waiting',
    )
    const contents = state.windows[0]!.webContents
    contents.off = () => {
      throw new Error('private optional off failure')
    }
    await state.service.close(opened.attemptId)
    assert.equal(state.windows[0]!.destroyed, true)
    const length = records.length
    contents.emit('console-message', {
      level: 'error',
      message: 'private optional retained observer',
    })
    assert.equal(records.length, length)
    assert.equal(JSON.stringify(records).includes('private optional'), false)
  } finally {
    await state.service.closeAll()
    globalThis.fetch = originalFetch
  }
})

test('Main metadata deadline aborts HTTP and a late success cannot focus or create a window', async () => {
  const originalFetch = globalThis.fetch
  const records: ManagementLoginDiagnostic[] = []
  const state = setup(undefined, {
    metadataTimeoutMs: 20,
    onDiagnostic: (record) => records.push(record),
  })
  let finish!: (response: Response) => void
  let signal!: AbortSignal
  globalThis.fetch = (_url, options) => {
    signal = options!.signal as AbortSignal
    return new Promise((resolve) => {
      finish = resolve
    })
  }
  try {
    await assert.rejects(
      state.service.focusShop(state.parent, {
        shopId,
        teamId,
        platform: 'douyin',
        correlationId: input.recovery!.leaseId,
      }),
      /SHOP_LOGIN_REQUEST_TIMEOUT/,
    )
    assert.equal(signal.aborted, true)
    const failed = records.find(
      (record) =>
        record.phase === 'session_metadata' && record.event === 'error',
    )!
    assert.equal(failed.errorCode, 'REQUEST_TIMEOUT')
    assert.equal(failed.httpStatus, null)
    assert.equal(failed.correlationId, input.recovery!.leaseId)
    assert.ok((failed.elapsedMs ?? 0) >= 15)
    finish(Response.json({ ignored: 'private-fixture' }))
    await new Promise((resolve) => setImmediate(resolve))
    assert.equal(state.windows.length, 0)
    assert.equal(JSON.stringify(records).includes('private-fixture'), false)
    assert.equal(
      records.some(
        (record) =>
          record.phase === 'session_metadata' && record.event === 'finish',
      ),
      false,
    )
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('cancelling an open while profile load is pending prevents late BrowserWindow creation', async () => {
  let finish!: (result: null) => void
  const state = setup({
    load: () =>
      new Promise((resolve) => {
        finish = resolve
      }),
    async save() {},
  })
  const attemptId = input.recovery!.leaseId
  const pending = state.service.open(state.parent, {
    ...input,
    attemptId,
    correlationId: attemptId,
  })
  await state.service.close(attemptId)
  finish(null)
  await assert.rejects(pending, /SHOP_LOGIN_CONTEXT_CHANGED/)
  assert.equal(state.windows.length, 0)
  assert.equal(state.captures(), 0)
})

test('authentication preparation failure is AUTH_REQUIRED with no GET-request event or fetch', async () => {
  const originalFetch = globalThis.fetch
  const originalCookies = loginSession.cookies.get
  const records: ManagementLoginDiagnostic[] = []
  const state = setup(undefined, {
    onDiagnostic: (record) => records.push(record),
  })
  let calls = 0
  loginSession.cookies.get = async () => []
  globalThis.fetch = async () => {
    calls++
    return Response.json({})
  }
  try {
    await assert.rejects(
      state.service.focusShop(state.parent, {
        shopId,
        teamId,
        platform: 'douyin',
      }),
      /SHOP_LOGIN_AUTH_REQUIRED/,
    )
    assert.equal(calls, 0)
    assert.equal(
      records.some((record) => record.event === 'request'),
      false,
    )
    assert.equal(
      records.find(
        (record) =>
          record.phase === 'session_metadata' && record.event === 'error',
      )?.errorCode,
      'AUTH_REQUIRED',
    )
  } finally {
    loginSession.cookies.get = originalCookies
    globalThis.fetch = originalFetch
  }
})

test('GET attempt and safe DNS code/errno are retained without URL, error message or cause contents', async () => {
  const originalFetch = globalThis.fetch
  const records: ManagementLoginDiagnostic[] = []
  const state = setup(undefined, {
    onDiagnostic: (record) => records.push(record),
  })
  globalThis.fetch = async () => {
    throw new TypeError('private-fixture', {
      cause: { code: 'ENOTFOUND', errno: -3008, private: 'private-fixture' },
    })
  }
  try {
    await assert.rejects(
      state.service.focusShop(state.parent, {
        shopId,
        teamId,
        platform: 'douyin',
      }),
      /SHOP_LOGIN_NETWORK_ERROR/,
    )
    assert.equal(
      records.some(
        (record) =>
          record.phase === 'session_metadata' && record.event === 'request',
      ),
      true,
    )
    const failed = records.find(
      (record) =>
        record.phase === 'session_metadata' && record.event === 'error',
    )!
    assert.equal(failed.errorCode, 'ENOTFOUND')
    assert.equal(failed.errno, -3008)
    assert.equal(JSON.stringify(records).includes('private-fixture'), false)
  } finally {
    globalThis.fetch = originalFetch
  }
})

test('diagnostic baseline: empty profile load rejection closes the child and releases without a save', async () => {
  const originalFetch = globalThis.fetch
  const requests: string[] = []
  globalThis.fetch = async (_url, init) => {
    requests.push(init?.method ?? 'GET')
    return new Response(null, { status: 204 })
  }
  const failure = Object.assign(new Error('synthetic navigation failure'), {
    code: 'ERR_SYNTHETIC_NAVIGATION',
  })
  const state = setup(undefined, { load: failure })
  try {
    await assert.rejects(state.service.open(state.parent, input), failure)
    assert.equal(state.windows.length, 1)
    assert.equal(state.windows[0]!.destroyed, true)
    assert.equal(state.parent.isDestroyed(), false)
    assert.equal(state.captures(), 0)
    assert.deepEqual(requests, ['DELETE'])
  } finally {
    await state.service.closeAll()
    globalThis.fetch = originalFetch
  }
})

test('diagnostic baseline: detection context failure becomes failed before Renderer cancellation closes the child', async () => {
  const originalFetch = globalThis.fetch
  const requests: string[] = []
  globalThis.fetch = async (_url, init) => {
    requests.push(init?.method ?? 'GET')
    return new Response(null, { status: 204 })
  }
  const state = setup(undefined, {
    detection: new Error('synthetic document-context failure'),
  })
  try {
    const opened = await state.service.open(state.parent, input)
    assert.equal(opened.profileReused, false)
    const status = await state.service.getStatus(opened.attemptId)
    assert.equal(status.status, 'failed')
    assert.equal(state.windows[0]!.destroyed, false)
    assert.equal(state.captures(), 0)
    // The existing Renderer handles this status by cancelling the attempt.
    await state.service.close(opened.attemptId)
    assert.equal(state.windows[0]!.destroyed, true)
    assert.equal(state.parent.isDestroyed(), false)
    assert.deepEqual(requests, ['DELETE'])
  } finally {
    await state.service.closeAll()
    globalThis.fetch = originalFetch
  }
})

test('development diagnostics whitelist navigation code/errno and explicit close reason, never exception text or URL', async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => new Response(null, { status: 204 })
  const records: ManagementLoginDiagnostic[] = []
  const failure = Object.assign(new Error('private exception text'), {
    code: 'ERR_SYNTHETIC_NAVIGATION',
    errno: -777,
    url: 'private navigation value',
  })
  const state = setup(undefined, {
    load: failure,
    onDiagnostic: (record) => records.push(record),
  })
  try {
    await assert.rejects(state.service.open(state.parent, input), failure)
    const failed = records.find(
      (record) => record.phase === 'load' && record.event === 'error',
    )!
    assert.equal(failed.errorCode, 'ERR_SYNTHETIC_NAVIGATION')
    assert.equal(failed.errno, -777)
    assert.equal(failed.mainFrameLoading, false)
    assert.ok(
      records.some(
        (record) =>
          record.event === 'closed' && record.closeReason === 'load_failed',
      ),
    )
    const serialized = JSON.stringify(records)
    assert.ok(!serialized.includes('private'))
    assert.ok(!serialized.includes('isolated-test'))
    assert.deepEqual(
      Object.keys(failed).sort(),
      [
        'timestamp',
        'attemptId',
        'correlationId',
        'source',
        'phase',
        'event',
        'errorCode',
        'errno',
        'isMainFrame',
        'mainFrameLoading',
        'navigationSequence',
        'closeReason',
      ].sort(),
    )
  } finally {
    await state.service.closeAll()
    globalThis.fetch = originalFetch
  }
})

test('development diagnostics distinguish capture error and Frame navigation without reflecting supplied content', async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => new Response(null, { status: 204 })
  const records: ManagementLoginDiagnostic[] = []
  const state = setup(undefined, {
    capture: Object.assign(new Error('private capture message'), {
      code: 'not-a-code-private',
      errno: 'private',
    }),
    onDiagnostic: (record) => records.push(record),
  })
  try {
    const opened = await state.service.open(state.parent, input)
    state.windows[0]!.loading = true
    state.windows[0]!.webContents.emit('did-start-navigation', {
      isMainFrame: true,
      url: 'private',
    })
    state.windows[0]!.webContents.emit(
      'did-fail-provisional-load',
      {},
      -3,
      'private description',
      'private URL',
      true,
    )
    const status = await state.service.getStatus(opened.attemptId)
    assert.equal(status.status, 'failed')
    const failed = records.find(
      (record) => record.phase === 'capture' && record.event === 'error',
    )!
    assert.equal(failed.errorCode, null)
    assert.equal(failed.errno, null)
    assert.ok(
      records.some(
        (record) =>
          record.errno === -3 &&
          record.isMainFrame === true &&
          record.mainFrameLoading === true,
      ),
    )
    await state.service.close(opened.attemptId)
    assert.ok(
      records.some(
        (record) =>
          record.event === 'closed' &&
          record.closeReason === 'renderer_request',
      ),
    )
    assert.ok(!JSON.stringify(records).includes('private'))
  } finally {
    await state.service.closeAll()
    globalThis.fetch = originalFetch
  }
})

test('a failed diagnostic sink cannot close a healthy window or fail identity capture', async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => new Response(null, { status: 204 })
  const state = setup(undefined, {
    onDiagnostic() {
      throw new Error('sink offline')
    },
  })
  try {
    const opened = await state.service.open(state.parent, input)
    assert.equal(
      (await state.service.getStatus(opened.attemptId)).status,
      'identified',
    )
    assert.equal(state.windows[0]!.destroyed, false)
  } finally {
    await state.service.closeAll()
    globalThis.fetch = originalFetch
  }
})

test('diagnostic property access never replaces the original error or changes cleanup', async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => new Response(null, { status: 204 })
  const failure = new Error('original navigation failure')
  Object.defineProperty(failure, 'code', {
    get() {
      throw new Error('diagnostic property unavailable')
    },
  })
  const state = setup(undefined, { load: failure })
  try {
    await assert.rejects(state.service.open(state.parent, input), failure)
    assert.equal(state.windows[0]!.destroyed, true)
  } finally {
    await state.service.closeAll()
    globalThis.fetch = originalFetch
  }
})

test('closed diagnostics survive destroyed-window getters, without changing manual cancellation or lease cleanup', async () => {
  const originalFetch = globalThis.fetch
  const requests: string[] = []
  globalThis.fetch = async (_url, init) => {
    requests.push(init?.method ?? 'GET')
    return new Response(null, { status: 204 })
  }
  const records: ManagementLoginDiagnostic[] = []
  const state = setup(undefined, {
    onDiagnostic: (record) => records.push(record),
  })
  try {
    const opened = await state.service.open(state.parent, input)
    const window = state.windows[0]!
    const contents = window.webContents
    Object.defineProperty(window, 'webContents', {
      get() {
        if (window.destroyed) throw new Error('private destroyed native getter')
        return contents
      },
    })
    window.close()
    await new Promise((resolve) => setImmediate(resolve))
    const status = await state.service.getStatus(opened.attemptId)
    assert.equal(status.status, 'closed')
    assert.equal(status.sessionCaptured, false)
    // The Renderer sees closed and performs its existing cleanup afterward.
    await state.service.close(opened.attemptId)
    const closed = records.find((record) => record.event === 'closed')
    assert.ok(closed)
    assert.equal(closed.phase, 'close')
    assert.equal(closed.closeReason, 'window_closed_without_request')
    assert.equal(closed.mainFrameLoading, null)
    assert.deepEqual(
      records
        .filter((record) => record.phase === 'close')
        .map((record) => record.event),
      ['closed', 'request'],
    )
    assert.deepEqual(requests, ['DELETE'])
    assert.equal(state.captures(), 0)
    assert.equal(state.parent.isDestroyed(), false)
    assert.ok(!JSON.stringify(records).includes('private'))
  } finally {
    await state.service.closeAll()
    globalThis.fetch = originalFetch
  }
})

test('unreadable optional frame state does not drop diagnostic events or affect identity capture', async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => new Response(null, { status: 204 })
  const records: ManagementLoginDiagnostic[] = []
  const state = setup(undefined, {
    onDiagnostic: (record) => records.push(record),
  })
  try {
    const opened = await state.service.open(state.parent, input)
    state.windows[0]!.webContents.isLoadingMainFrame = () => {
      throw new Error('private native frame state unavailable')
    }
    const status = await state.service.getStatus(opened.attemptId)
    assert.equal(status.status, 'identified')
    assert.equal(state.captures(), 1)
    assert.equal(state.windows[0]!.destroyed, false)
    const detection = records.filter((record) => record.phase === 'detect')
    assert.deepEqual(
      detection.map((record) => record.event),
      ['start', 'finish'],
    )
    assert.ok(detection.every((record) => record.mainFrameLoading === null))
    assert.ok(!JSON.stringify(records).includes('private'))
  } finally {
    await state.service.closeAll()
    globalThis.fetch = originalFetch
  }
})

test('existing shop: single capture/save, retain browsing without lease, focus only, close/reopen synchronizes again', async () => {
  const originalFetch = globalThis.fetch
  let saves = 0
  globalThis.fetch = async (_url, init) => {
    if (init?.method === 'POST') saves++
    return Response.json({
      shop_id: shopId,
      status: 'valid',
      version: 4,
      validated_at: '2026-10-11T09:00:01Z',
      cookie_updates_applied: 0,
      used_cached_validation: false,
    })
  }
  const state = setup()
  try {
    const opened = await state.service.open(state.parent, input)
    const [first, second] = await Promise.all([
      state.service.getStatus(opened.attemptId),
      state.service.getStatus(opened.attemptId),
    ])
    assert.equal(first.status, 'identified')
    assert.equal(second.status, 'identified')
    assert.equal(state.captures(), 1)
    assert.equal(state.windows[0]!.destroyed, false)
    await Promise.all([
      state.service.refresh(opened.attemptId),
      state.service.refresh(opened.attemptId),
    ])
    assert.equal(saves, 1)
    assert.equal(state.windows[0]!.destroyed, false)
    assert.ok(state.buffers[0]!.every((value) => value === 0))
    await assert.rejects(state.service.getStatus(opened.attemptId), /不存在/)
    assert.equal(
      await state.service.focusShop(state.parent, {
        shopId,
        teamId,
        platform: 'douyin',
      }),
      true,
    )
    assert.equal(saves, 1)
    assert.equal(state.captures(), 1)
    state.windows[0]!.close()
    assert.equal(
      await state.service.focusShop(state.parent, {
        shopId,
        teamId,
        platform: 'douyin',
      }),
      false,
    )
    const reopened = await state.service.open(state.parent, input)
    assert.notEqual(reopened.attemptId, opened.attemptId)
    await state.service.getStatus(reopened.attemptId)
    assert.equal(state.captures(), 2)
  } finally {
    await state.service.closeAll()
    globalThis.fetch = originalFetch
  }
})

test('first onboarding capture still auto-closes; premature close clears candidate; failed validation is not success', async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () =>
    Response.json({ message: '本次验证未完成' }, { status: 502 })
  const state = setup()
  try {
    const onboarding = await state.service.open(state.parent, {
      platform: 'douyin',
      teamId,
    })
    const status = await state.service.getStatus(onboarding.attemptId)
    assert.equal(status.status, 'identified')
    assert.equal(status.sessionCaptured, true)
    assert.equal(state.windows[0]!.destroyed, true)
    const recovery = await state.service.open(state.parent, input)
    await state.service.getStatus(recovery.attemptId)
    await assert.rejects(
      state.service.refresh(recovery.attemptId),
      /验证未完成/,
    )
    state.windows[1]!.close()
    const cancelled = await state.service.getStatus(recovery.attemptId)
    assert.equal(cancelled.status, 'closed')
    assert.equal(cancelled.sessionCaptured, false)
    assert.ok(state.buffers[1]!.every((value) => value === 0))
  } finally {
    await state.service.closeAll()
    globalThis.fetch = originalFetch
  }
})

test('completed shared shop focuses the same window after Team change, with current authorization and no new capture/save', async () => {
  const originalFetch = globalThis.fetch
  const state = setup()
  const otherTeamId = 'e29a1e70-0c58-4f16-bd24-58e4d8cfda90'
  let saves = 0
  let focusedTeam: string | null = null
  globalThis.fetch = async (_url, init) => {
    if (init?.method === 'POST') saves++
    else focusedTeam = new Headers(init?.headers).get('x-team-id')
    return Response.json({
      shop_id: shopId,
      status: 'valid',
      version: 4,
      validated_at: '2026-10-11T09:00:01Z',
      used_cached_validation: false,
      cookie_updates_applied: 0,
    })
  }
  try {
    const opened = await state.service.open(state.parent, input)
    await state.service.getStatus(opened.attemptId)
    await state.service.refresh(opened.attemptId)
    assert.equal(
      await state.service.focusShop(state.parent, {
        platform: 'douyin',
        shopId,
        teamId: otherTeamId,
      }),
      true,
    )
    assert.equal(focusedTeam, otherTeamId)
    assert.equal(state.windows.length, 1)
    assert.equal(state.windows[0]!.focused, 1)
    assert.equal(state.captures(), 1)
    assert.equal(saves, 1)
    // Even a stale caller that bypasses focus cannot open another Shop window.
    await assert.rejects(
      state.service.open(state.parent, {
        ...input,
        teamId: otherTeamId,
      }),
      /已打开/,
    )
    assert.equal(state.windows.length, 1)
    assert.equal(saves, 1)
  } finally {
    await state.service.closeAll()
    globalThis.fetch = originalFetch
  }
})

test('a retained window never bypasses current personnel authorization', async () => {
  const originalFetch = globalThis.fetch
  const state = setup()
  globalThis.fetch = async () =>
    Response.json({ message: 'forbidden' }, { status: 403 })
  try {
    await state.service.open(state.parent, input)
    await assert.rejects(
      state.service.focusShop(state.parent, {
        shopId,
        teamId,
        platform: 'douyin',
      }),
      /SHOP_LOGIN_FORBIDDEN/,
    )
    assert.equal(state.windows[0]!.focused, 0)
  } finally {
    await state.service.closeAll()
    globalThis.fetch = originalFetch
  }
})

test('same-shop concurrent opens coalesce while the profile is loading', async () => {
  const originalFetch = globalThis.fetch
  globalThis.fetch = async () => new Response(null, { status: 204 })
  let finish!: (value: null) => void
  const state = setup({
    load: () =>
      new Promise((resolve) => {
        finish = resolve
      }),
    async save() {},
  })
  try {
    const first = state.service.open(state.parent, input)
    const second = state.service.open(state.parent, input)
    await assert.rejects(
      state.service.open(state.parent, {
        ...input,
        teamId: 'e29a1e70-0c58-4f16-bd24-58e4d8cfda90',
      }),
      /不匹配/,
    )
    finish(null)
    const [a, b] = await Promise.all([first, second])
    assert.equal(a.attemptId, b.attemptId)
    assert.equal(state.windows.length, 1)
  } finally {
    await state.service.closeAll()
    globalThis.fetch = originalFetch
  }
})

test('cached validation and cancellation cannot claim a fresh sync', async () => {
  const originalFetch = globalThis.fetch
  const state = setup()
  globalThis.fetch = async () =>
    Response.json({
      shop_id: shopId,
      status: 'valid',
      version: 4,
      validated_at: '2026-10-11T09:00:01Z',
      used_cached_validation: true,
    })
  try {
    const opened = await state.service.open(state.parent, input)
    await state.service.getStatus(opened.attemptId)
    await assert.rejects(state.service.refresh(opened.attemptId), /不完整/)
    let finish!: (response: Response) => void
    globalThis.fetch = async (_url, init) =>
      init?.method === 'POST'
        ? new Promise((resolve) => {
            finish = resolve
          })
        : new Response(null, { status: 204 })
    const saving = state.service.refresh(opened.attemptId)
    await new Promise((resolve) => setImmediate(resolve))
    const rejected = assert.rejects(saving, /已取消/)
    await state.service.close(opened.attemptId)
    finish(
      Response.json({
        shop_id: shopId,
        status: 'valid',
        version: 4,
        validated_at: '2026-10-11T09:00:01Z',
        used_cached_validation: false,
      }),
    )
    await rejected
    assert.ok(state.buffers[0]!.every((value) => value === 0))
  } finally {
    await state.service.closeAll()
    globalThis.fetch = originalFetch
  }
})

test('exit closes retained and pending windows before offline lease release completes', async () => {
  const originalFetch = globalThis.fetch
  const state = setup()
  globalThis.fetch = async () =>
    Response.json({
      shop_id: shopId,
      status: 'valid',
      version: 4,
      validated_at: '2026-10-11T09:00:01Z',
      used_cached_validation: false,
      cookie_updates_applied: 0,
    })
  try {
    const completed = await state.service.open(state.parent, input)
    await state.service.getStatus(completed.attemptId)
    await state.service.refresh(completed.attemptId)
    await state.service.open(state.parent, {
      ...input,
      recovery: { ...input.recovery!, shopId: teamId },
    })
    let finish!: (response: Response) => void
    globalThis.fetch = async () =>
      new Promise((resolve) => {
        finish = resolve
      })
    const closing = state.service.closeAll()
    assert.ok(state.windows.every((window) => window.destroyed))
    await new Promise((resolve) => setImmediate(resolve))
    finish(new Response(null, { status: 204 }))
    await closing
    await assert.rejects(state.service.open(state.parent, input), /正在退出/)
  } finally {
    globalThis.fetch = originalFetch
  }
})
