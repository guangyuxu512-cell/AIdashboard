import { defineComponent, reactive } from 'vue'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createOperatingDashboardFixture } from '../__fixtures__/operating-dashboard.fixture'
import { buildOperatingDashboardRead } from './dashboard'
import type { OperatingDashboardSessionRecovery } from './types'
import { useOperatingDashboard } from './useOperatingDashboard'

const calls = vi.hoisted(() => ({
  read: vi.fn(),
  recover: vi.fn(),
  collection: vi.fn(),
  update: vi.fn(),
  mock: vi.fn(),
  auth: {} as {
    currentUser: { userId: string }
    activeTeamId: string
    isSuperAccount: boolean
  },
}))
vi.mock('@/shared/api', () => ({
  apiMode: 'real',
  getErrorMessage: (error: Error) => error.message,
}))
vi.mock('../api/operating-dashboard-api', () => ({
  operatingDashboardApi: {
    read: calls.read,
    recoverCollectionItem: calls.recover,
    getCollection: calls.collection,
    requestCollectionUpdate: calls.update,
  },
}))
vi.mock('./mock-source', () => ({
  createOperatingDashboardMockSource: calls.mock,
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => calls.auth }))

const target: OperatingDashboardSessionRecovery = {
  collectionJobId: 'original-job',
  collectionItemId: 'original-item',
  sessionVersion: 3,
  requiresValidation: true,
}
const resources: { wrapper: VueWrapper; client: QueryClient }[] = []

function snapshot(complete = false) {
  const now = new Date('2026-10-17T03:00:00Z')
  const read = buildOperatingDashboardRead(
    createOperatingDashboardFixture(now),
    {
      datePreset: 'yesterday',
      customDateRange: null,
      platform: null,
      shopId: null,
    },
    now,
  )
  read.collectionAvailable = true
  read.coverage = {
    state: 'available',
    supportedShopCount: 1,
    collectedShopDays: complete ? 1 : 0,
    totalShopDays: 1,
    missingShopDays: complete ? 0 : 1,
    missingSamples: complete
      ? []
      : [
          {
            shopId: 'shop',
            shopName: 'synthetic recovery shop',
            businessDate: '2026-10-16',
            state: 'failed',
            failureReason: '历史会话校验失败',
            sessionRecovery: target,
          },
        ],
    missingSamplesTruncated: false,
    manualBackfillRequired: !complete,
  }
  return read
}

function job(status: 'pending' | 'succeeded' = 'pending') {
  return {
    collection_job_id: 'recovery-job',
    status,
    counts: {
      pending: status === 'pending' ? 1 : 0,
      running: 0,
      succeeded: status === 'succeeded' ? 1 : 0,
      failed: 0,
      skipped: 0,
      paused_reauthorization: 0,
    },
    items: [],
  }
}

async function setup() {
  let flow!: ReturnType<typeof useOperatingDashboard>
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  const wrapper = mount(
    defineComponent({
      setup() {
        flow = useOperatingDashboard()
        return () => null
      },
    }),
    { global: { plugins: [[VueQueryPlugin, { queryClient: client }]] } },
  )
  resources.push({ wrapper, client })
  await vi.waitFor(() => expect(flow.read.value).toBeDefined())
  return flow
}

beforeEach(() => {
  vi.resetAllMocks()
  calls.auth = reactive({
    currentUser: { userId: 'person' },
    activeTeamId: 'team',
    isSuperAccount: false,
  })
  calls.read.mockResolvedValue(snapshot())
  calls.collection.mockResolvedValue(job('succeeded'))
})
afterEach(() => {
  for (const { wrapper, client } of resources.splice(0)) {
    wrapper.unmount()
    client.clear()
  }
})

describe('explicit operating-data recovery with the actual Query client', () => {
  it('never auto-recovers from a read, deduplicates clicks and refreshes facts after the existing Job finishes', async () => {
    let accept!: (value: ReturnType<typeof job>) => void
    calls.recover.mockImplementation(
      () =>
        new Promise((resolve) => {
          accept = resolve
        }),
    )
    calls.read
      .mockResolvedValueOnce(snapshot())
      .mockResolvedValue(snapshot(true))
    const flow = await setup()
    expect(calls.recover).not.toHaveBeenCalled()
    flow.recoverCollectionItem(target)
    flow.recoverCollectionItem(target)
    await vi.waitFor(() => expect(calls.recover).toHaveBeenCalledTimes(1))
    expect(flow.refreshing.value).toBe(true)
    accept(job())
    await vi.waitFor(() =>
      expect(flow.read.value?.coverage.missingShopDays).toBe(0),
    )
    expect(calls.collection).toHaveBeenCalledWith('recovery-job')
    expect(flow.refreshFeedback.value?.tone).toBe('success')
    expect(calls.mock).not.toHaveBeenCalled()
  })

  it('keeps a rejected recovery as failure and leaves missing data visible without automatic retries', async () => {
    calls.recover.mockRejectedValue(new Error('会话版本已变化，请刷新后重试'))
    const flow = await setup()
    flow.recoverCollectionItem(target)
    await vi.waitFor(() =>
      expect(flow.refreshFeedback.value?.tone).toBe('error'),
    )
    expect(flow.refreshFeedback.value?.message).toContain('会话版本已变化')
    expect(flow.read.value?.coverage.missingShopDays).toBe(1)
    expect(calls.recover).toHaveBeenCalledTimes(1)
    expect(calls.collection).not.toHaveBeenCalled()
    expect(calls.mock).not.toHaveBeenCalled()
  })

  it('keeps an accepted pending Job busy before its first progress response', async () => {
    let complete!: (value: ReturnType<typeof job>) => void
    calls.recover.mockResolvedValue(job())
    calls.collection.mockImplementation(
      () =>
        new Promise((resolve) => {
          complete = resolve
        }),
    )
    const flow = await setup()
    flow.recoverCollectionItem(target)
    await vi.waitFor(() => expect(calls.collection).toHaveBeenCalledTimes(1))
    expect(flow.refreshing.value).toBe(true)
    flow.recoverCollectionItem(target)
    expect(calls.recover).toHaveBeenCalledTimes(1)
    complete(job('succeeded'))
    await vi.waitFor(() => expect(flow.refreshing.value).toBe(false))
  })

  it('rejects stale or fabricated UI targets before any mutation', async () => {
    const flow = await setup()
    flow.recoverCollectionItem({ ...target, sessionVersion: 2 })
    flow.recoverCollectionItem({ ...target, collectionItemId: 'other-item' })
    expect(calls.recover).not.toHaveBeenCalled()
    expect(calls.mock).not.toHaveBeenCalled()
  })

  it('ignores a late receipt after the current team changes without pretending to cancel server work', async () => {
    let accept!: (value: ReturnType<typeof job>) => void
    calls.recover.mockImplementation(
      () =>
        new Promise((resolve) => {
          accept = resolve
        }),
    )
    const flow = await setup()
    flow.recoverCollectionItem(target)
    await vi.waitFor(() => expect(calls.recover).toHaveBeenCalledTimes(1))
    calls.auth.activeTeamId = 'other-team'
    accept(job())
    await vi.waitFor(() => expect(flow.refreshing.value).toBe(false))
    expect(calls.collection).not.toHaveBeenCalled()
    expect(flow.refreshFeedback.value).toBeNull()
  })

  it('does not attach a late receipt after the page is disposed', async () => {
    let accept!: (value: ReturnType<typeof job>) => void
    calls.recover.mockImplementation(
      () =>
        new Promise((resolve) => {
          accept = resolve
        }),
    )
    const flow = await setup()
    flow.recoverCollectionItem(target)
    await vi.waitFor(() => expect(calls.recover).toHaveBeenCalledTimes(1))
    const resource = resources.pop()!
    resource.wrapper.unmount()
    accept(job())
    await flushPromises()
    expect(calls.collection).not.toHaveBeenCalled()
    expect(flow.refreshFeedback.value).toBeNull()
    resource.client.clear()
  })
})
