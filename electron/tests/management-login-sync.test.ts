import assert from 'node:assert/strict'
import test from 'node:test'
import { EventEmitter } from 'node:events'
import type { BrowserWindow, Session } from 'electron'
import { ManagementLoginService } from '../services/management-login-service'
import type { ManagementLoginOpenInput } from '../types'
import type { PlatformAuthAdapter } from '../services/platform-auth-adapter'
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
  webContents = { id: 42, session: loginSession, setWindowOpenHandler() {} }
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
  async loadURL() {}
  close() {
    if (!this.destroyed) {
      this.destroyed = true
      this.emit('closed')
    }
  }
}

function setup(profileMappingStore?: ManagementLoginProfileMappingStore) {
  const windows: WindowStub[] = []
  const buffers: Buffer[] = []
  let captures = 0
  const adapter: PlatformAuthAdapter = {
    platformCode: 'douyin',
    loginUrl: 'https://test.example/login',
    loginWindowTitle: 'isolated test',
    async detectLoginStatus() {
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
      windows.push(window)
      return window as unknown as BrowserWindow
    },
    fromPartition: () => loginSession,
    profileMappingStore: profileMappingStore ?? {
      async load() {
        return null
      },
      async save() {},
    },
  })
  return {
    service,
    windows,
    buffers,
    captures: () => captures,
    parent: new WindowStub() as unknown as BrowserWindow,
  }
}

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
      /forbidden/,
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
